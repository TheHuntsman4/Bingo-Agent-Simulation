# Functions to format messages from the console.
# NOTE: ONLY FORMATTING THE CONSOLE OUTPUTS, NOT HOW THE AGENT RESPONSES ARE PROCESSED OR HOW THEY WILL BE SAVED

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[0m\033[94m'
    OKCYAN = '\033[0m\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[0m\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def format_message(speaker: str, message: str) -> str:
    """Format a message for the console."""
    return f"{speaker}: {message}"

def format_message_with_color(speaker: str, message: str, color: str) -> str:
    """Format a message for the console with a specific color."""
    return f"{color}{speaker}: {message}{bcolors.ENDC}"

