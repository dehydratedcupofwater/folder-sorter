from pathlib import Path
import shutil
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading
import json
import argparse

# Ensures only one sort_folder() call runs at a time. 
sort_lock = threading.Lock()


def load_config(config_path: Path) -> dict:
    """Loads the extension, folder mapping from an external JSON file,
    so categories can be edited without touching the code."""
    with open(config_path, "r") as f:
        return json.load(f)


# Path(__file__).parent ensures config.json is always found next to
# this script, regardless of what directory the script is run from.
CONFIG_PATH = Path(__file__).parent / "config.json"
EXTENSION_MAPS = load_config(CONFIG_PATH)

# Files still being written by a browser (partial downloads) use these
# extensions. Ignores them so the program never moves/sorts an incomplete file.
IGNORED_EXTENSIONS: list[str] = [".crdownload", ".part", ".tmp"]


def build_extension_lookup(extension_map: dict) -> dict:
    """Flip {"Images": [".png", ".jpg"]} into {".png": "Images", ".jpg": "Images"}
    so looking up a file's destination folder is a fast dict lookup."""
    lookup = {}
    for folder_name, extensions in extension_map.items():
        for ext in extensions:
            lookup[ext] = folder_name
    return lookup


def sort_folder(target_folder: Path, extension_map: dict) -> None:
    """Scan target_folder (non-recursively) and move each file into a
    subfolder based on its extension. Unrecognized extensions are
    left untouched."""
    lookup = build_extension_lookup(extension_map)

    for item in target_folder.iterdir():
        if not item.is_file():
            continue  # skip subfolders, including created ones.

        extension = item.suffix.lower()
        if extension in IGNORED_EXTENSIONS:
            continue

        destination_folder_name = lookup.get(extension)
        if destination_folder_name is None:
            continue

        destination_folder = target_folder / destination_folder_name
        destination_folder.mkdir(exist_ok=True)
        destination_path = destination_folder / item.name

        # If a file with this name already exists at the destination,
        # find the next available name (photo.png -> photo_1.png, etc.)
        # instead of silently overwriting the existing file.
        if destination_path.exists():
            counter = 1
            while destination_path.exists():
                new_name = f"{item.stem}_{counter}{item.suffix}"
                destination_path = destination_folder / new_name
                counter += 1

        if not item.exists():
            continue  # another overlapping event already moved this file

        try:
            print(f"Moving: {item.name} -> {destination_folder_name}/", flush=True)
            shutil.move(str(item), str(destination_path))
        except FileNotFoundError:
            # Rare race: file vanished between the check above and the
            # move itself (another event got to it first). Safe to skip.
            print(f"Skipped {item.name} — already moved by another event.", flush=True)


class SorterHandler(FileSystemEventHandler):
    """watchdog calls the methods below automatically whenever something
    happens in the watched folder."""

    def __init__(self, target_folder: Path, extension_map: dict):
        self.target_folder = target_folder
        self.extension_map = extension_map

    def _is_top_level(self, path_str: str) -> bool:
        """True only if the changed file lives directly inside the
        watched folder, not in one of our own subfolders (Images/,
        Archives/, etc.). Prevents user moves, or later manual
        reorganizing inside those subfolders, from triggering
        needless full rescans."""
        return Path(path_str).parent == self.target_folder

    def on_created(self, event):
        if event.is_directory or not self._is_top_level(event.src_path):
            return
        with sort_lock:
            sort_folder(self.target_folder, self.extension_map)

    def on_moved(self, event):
        # Fires when a file is renamed in place for browser downloads.
        # (file.png.part -> file.png), which is a MOVE event.
        if event.is_directory or not self._is_top_level(event.dest_path):
            return
        with sort_lock:
            sort_folder(self.target_folder, self.extension_map)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Watch a folder and sort files by extension.")
    parser.add_argument("--folder", type=str, default=str(Path.home() / "Downloads"),
                        help="Folder to watch (default: ~/Downloads)")
    args = parser.parse_args()

    downloads_folder = Path(args.folder)

    if not downloads_folder.exists():
        print(f"Folder not found: {downloads_folder}")
    else:
        event_handler = SorterHandler(downloads_folder, EXTENSION_MAPS)

        observer = Observer()
        observer.schedule(event_handler, path=str(downloads_folder), recursive=False)
        observer.start()

        print(f"Watching {downloads_folder} — press Ctrl+C to stop.")

        try:
            # The Observer runs in its own background thread. Without
            # something keeping the main program alive, the script
            # would just exit immediately after start().
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
            print("\nStopped by user.")

        observer.join()  # wait for the background thread to fully shut down