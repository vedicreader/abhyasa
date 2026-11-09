"The host contract number: one integer that Leela reads before it builds the hosted app."

HOST_API = 1


def host_missing(required:int) -> str:
    "The one-line reason this Abhyasa is too old for a host that needs `required`, else an empty string."
    return f"Abhyasa too old: needs host API {required}, has {HOST_API}" if HOST_API < required else ""
