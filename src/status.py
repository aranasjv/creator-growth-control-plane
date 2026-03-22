from termcolor import colored


def _format(prefix: str, message: str) -> str:
    return f"{prefix} {message}".strip()


def error(message: str, show_emoji: bool = True) -> None:
    """
    Prints an error message.

    Args:
        message (str): The error message
        show_emoji (bool): Whether to show the prefix

    Returns:
        None
    """
    prefix = "[x]" if show_emoji else ""
    print(colored(_format(prefix, message), "red"))


def success(message: str, show_emoji: bool = True) -> None:
    """
    Prints a success message.

    Args:
        message (str): The success message
        show_emoji (bool): Whether to show the prefix

    Returns:
        None
    """
    prefix = "[ok]" if show_emoji else ""
    print(colored(_format(prefix, message), "green"))


def info(message: str, show_emoji: bool = True) -> None:
    """
    Prints an info message.

    Args:
        message (str): The info message
        show_emoji (bool): Whether to show the prefix

    Returns:
        None
    """
    prefix = "[i]" if show_emoji else ""
    print(colored(_format(prefix, message), "magenta"))


def warning(message: str, show_emoji: bool = True) -> None:
    """
    Prints a warning message.

    Args:
        message (str): The warning message
        show_emoji (bool): Whether to show the prefix

    Returns:
        None
    """
    prefix = "[!]" if show_emoji else ""
    print(colored(_format(prefix, message), "yellow"))


def question(message: str, show_emoji: bool = True) -> str:
    """
    Prints a question message and returns the user's input.

    Args:
        message (str): The question message
        show_emoji (bool): Whether to show the prefix

    Returns:
        user_input (str): The user's input
    """
    prefix = "[?]" if show_emoji else ""
    return input(colored(_format(prefix, message), "magenta"))
