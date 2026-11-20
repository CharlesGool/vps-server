"""Which input a request was refused for: the ``field`` and ``reason`` an API error may add.

``field`` is the key in the JSON request body, with dots for nested keys (``resetSpec.time``);
``reason`` is one of REASONS. The error code itself stays what it was, so pages and scripts
that look up the code keep working; the two keys only say which input and why. They are added
only where the input is certain, never guessed.
"""

REASONS = (
    "required",     # missing or empty
    "type",         # the wrong JSON type (text where a number belongs, say)
    "format",       # not in the expected form, or not one of the allowed choices
    "range",        # a number, date or count outside what is allowed
    "too_long",     # text longer than allowed
    "too_short",    # text shorter than allowed (a secret key, say)
    "exists",       # the name, address or value is already taken
    "not_found",    # what the value names does not exist
    "past",         # a time that has already passed
    "port_in_use",  # the port is taken by something else
)


class FieldError(ValueError):
    """A request refused because of one input. A ValueError, so callers that catch those still do."""

    def __init__(self, field, reason, message=None):
        if reason not in REASONS:
            raise AssertionError("unknown reason " + repr(reason))
        super().__init__(message or f"{field}: {reason}")
        self.field, self.reason = field, reason


def details(error):
    """The ``field`` and ``reason`` keys for an API error response, or {} when ``error`` names no input."""
    if isinstance(error, FieldError):
        return {"field": error.field, "reason": error.reason}
    return {}


def text(body, name, limit, *, required=False, strip=False):
    """A text value of ``body`` (missing or null is ""); FieldError for the wrong type, a too long or a missing one."""
    value = body.get(name)
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise FieldError(name, "type")
    if strip:
        value = value.strip()
    if len(value) > limit:
        raise FieldError(name, "too_long")
    if required and not value.strip():
        raise FieldError(name, "required")
    return value


def integer(body, name, low=None, high=None, *, required=True):
    """An integer value of ``body`` (bool is not one), within [low, high]; None when absent and not required."""
    value = body.get(name)
    if value is None and not required:
        return None
    if value is None:
        raise FieldError(name, "required")
    if type(value) is not int:
        raise FieldError(name, "type")
    if (low is not None and value < low) or (high is not None and value > high):
        raise FieldError(name, "range")
    return value


def schedule_error(error, spec, prefix="spec"):
    """A scheduler.ScheduleError for ``spec`` (a schedule as scheduler.normalize_spec takes it) as a FieldError.

    ``prefix`` is the spec's key in the request body. A message this does not know names the
    whole spec.
    """
    message = str(error)
    if isinstance(spec, str):
        # The oldest form: a bare cron expression.
        return FieldError(prefix, "range" if message == "value out of range" else "format", message)
    if not isinstance(spec, dict):
        return FieldError(prefix, "required" if spec is None else "type", message)
    if message == "that time has already passed":
        return FieldError(prefix + ".date", "past", message)
    if spec.get("mode") == "cron" and not (isinstance(spec.get("expr"), str) and spec["expr"].strip()):
        expr = spec.get("expr")
        return FieldError(prefix + ".expr", "required" if expr is None or isinstance(expr, str) else "type", message)
    if message == "invalid schedule":
        if spec.get("mode") == "cron":
            return FieldError(prefix + ".expr", "too_long" if isinstance(spec.get("expr"), str) else "format", message)
        return FieldError(prefix + ".mode", "required" if spec.get("mode") is None else "format", message)
    if message in ("a schedule has five fields", "invalid step", "invalid field"):
        return FieldError(prefix + ".expr", "format", message)
    if message == "value out of range":
        return FieldError(prefix + ".expr", "range", message)
    if message == "invalid interval":
        unit = spec.get("unit")
        if unit not in ("minutes", "hours", "days"):
            return FieldError(prefix + ".unit", "format", message)
        n = spec.get("n")
        if isinstance(n, bool) or not isinstance(n, (int, str)):
            return FieldError(prefix + ".n", "type", message)
        try:
            int(n)
        except ValueError:
            return FieldError(prefix + ".n", "format", message)
        return FieldError(prefix + ".n", "range", message)
    if message == "invalid time":
        return FieldError(prefix + ".time", "required" if not spec.get("time") else "format", message)
    if message == "invalid days":
        days = spec.get("days")
        return FieldError(prefix + ".days", "required" if days == [] or days is None else "format", message)
    if message == "invalid day":
        return FieldError(prefix + ".day", "range", message)
    if message == "invalid date":
        if spec.get("mode") == "yearly":
            month = spec.get("month")
            if type(month) is not int or not 1 <= month <= 12:
                return FieldError(prefix + ".month", "range", message)
            return FieldError(prefix + ".day", "range", message)
        return FieldError(prefix + ".date", "required" if not spec.get("date") else "format", message)
    return FieldError(prefix, "format", message)
