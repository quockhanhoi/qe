import os
import sys
import time
from .colors import colors

qkhanhzcoder = colors.qkhanhzdz

textlines = [
    "                                                                         ",
    "  ██████╗ ██╗  ██╗██╗  ██╗ █████╗ ███╗   ██╗██╗  ██╗███████╗             ",
    " ██╔═══██╗██║ ██╔╝██║  ██║██╔══██╗████╗  ██║██║  ██║╚══███╔╝             ",
    " ██║   ██║█████╔╝ ███████║███████║██╔██╗ ██║███████║  ███╔╝              ",
    " ██║▄▄ ██║██╔═██╗ ██╔══██║██╔══██║██║╚██╗██║██╔══██║ ███╔╝               ",
    " ╚██████╔╝██║  ██╗██║  ██╗██║  ██║██║ ╚████║██║  ██║███████╗             ",
    "  ╚══▀▀═╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝╚══════╝             ",
    "                                                                         "
]

carlines = [
    "        /\\",
    "   <===[  |D",
    "   <===[  |D",
    "        \\/"
]

frames = []
steps = 40

for i in range(steps + 1):
    progress = int((i / steps) * len(textlines[2]))
    frame = ""
    frame += f"{qkhanhzcoder[0]}{textlines[0][:progress]}\n"
    frame += f"{qkhanhzcoder[1]}{textlines[1][:progress]}\n"
    frame += f"{qkhanhzcoder[2]}{textlines[2][:progress]}{carlines[0]}\n"
    frame += f"{qkhanhzcoder[3]}{textlines[3][:progress]}{carlines[1]}\n"
    frame += f"{qkhanhzcoder[0]}{textlines[4][:progress]}{carlines[2]}\n"
    frame += f"{qkhanhzcoder[1]}{textlines[5][:progress]}{carlines[3]}\n"
    frame += f"{qkhanhzcoder[2]}{textlines[6][:progress]}\n"
    frame += f"{qkhanhzcoder[3]}{textlines[7][:progress]}\n"
    frames.append(frame)

def intro():
    # Windows-specific non-blocking key check if possible, else skip skip-check
    continue_animation = True
    
    # Simple check for 's' to skip if on Windows and msvcrt is available
    try:
        import msvcrt
        has_msvcrt = True
    except ImportError:
        has_msvcrt = False

    for frame in frames:
        if has_msvcrt:
            if msvcrt.kbhit():
                if msvcrt.getch().decode().lower() == 's':
                    continue_animation = False
                    break

        sys.stdout.write('\x1b[2J\x1b[H')
        sys.stdout.write(frame)
        sys.stdout.flush()
        time.sleep(0.03)

    sys.stdout.write('\x1b[2J\x1b[H')
    final_frame = (
        f"{qkhanhzcoder[0]}{textlines[0]}\n"
        f"{qkhanhzcoder[1]}{textlines[1]}\n"
        f"{qkhanhzcoder[2]}{textlines[2]}{carlines[0]}\n"
        f"{qkhanhzcoder[3]}{textlines[3]}{carlines[1]}\n"
        f"{qkhanhzcoder[0]}{textlines[4]}{carlines[2]}\n"
        f"{qkhanhzcoder[1]}{textlines[5]}{carlines[3]}\n"
        f"{qkhanhzcoder[2]}{textlines[6]}\n"
        f"{qkhanhzcoder[3]}{textlines[7]}\n"
    )
    sys.stdout.write(final_frame)
    sys.stdout.write('\n')
    sys.stdout.flush()
