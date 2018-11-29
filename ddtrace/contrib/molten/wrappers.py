import wrapt
import molten

from ... import Pin
from ...utils.importlib import func_name

def trace_wrapped(resource, wrapped, *args, **kwargs):
    pin = Pin.get_from(molten)
    if not pin or not pin.enabled():
        return wrapped(*args, **kwargs)

    with pin.tracer.trace(func_name(wrapped), service=pin.service, resource=resource):
        return wrapped(*args, **kwargs)


def trace_func(resource):
    """Trace calls to function using provided resource name
    """
    @wrapt.function_wrapper
    def _trace_func(wrapped, instance, args, kwargs):
        pin = Pin.get_from(molten)

        if not pin or not pin.enabled():
            return wrapped(*args, **kwargs)

        with pin.tracer.trace(func_name(wrapped), service=pin.service, resource=resource):
            return wrapped(*args, **kwargs)

    return _trace_func


class WrapperComponent(wrapt.ObjectProxy):
    """ Tracing of components """
    def can_handle_parameter(self, *args, **kwargs):
        func = self.__wrapped__.can_handle_parameter
        cname = func_name(self.__wrapped__)
        resource = '{}.{}'.format(cname, func.__name__)
        return trace_wrapped(resource, func, *args, **kwargs)

    # TODO[tahir]: the signature of a wrapped resolve method causes DIError to
    # be thrown since paramter types cannot be determined


class WrapperRenderer(wrapt.ObjectProxy):
    """ Tracing of renderers """
    def render(self, *args, **kwargs):
        func = self.__wrapped__.render
        cname = func_name(self.__wrapped__)
        resource = '{}.{}'.format(cname, func.__name__)
        return trace_wrapped(resource, func, *args, **kwargs)


class WrapperMiddleware(wrapt.ObjectProxy):
    """ Tracing of callable functional-middleware """
    def __call__(self, *args, **kwargs):
        func = self.__wrapped__.__call__
        cname = func_name(self.__wrapped__)
        # only use callable class name for resource name
        resource = '{}'.format(cname)
        return trace_wrapped(resource, func, *args, **kwargs)


class WrapperRouter(wrapt.ObjectProxy):
    """ Tracing of router on the way back from a matched route """
    def match(self, *args, **kwargs):
        # catch matched route and wrap tracer around its handler and set root span resource
        func = self.__wrapped__.match
        route_and_params = func(*args, **kwargs)

        pin = Pin.get_from(molten)
        if not pin or not pin.enabled():
            return route_and_params

        if route_and_params is not None:
            route, params = route_and_params

            resource = '{} {}'.format(
                route.method,
                route.template,
            )

            route.handler = trace_func(resource)(route.handler)

            # update root span resource while we know the matched route
            root_span = pin.tracer.current_root_span()
            if root_span:
                root_span.resource = resource

            return route, params

        return route_and_params
