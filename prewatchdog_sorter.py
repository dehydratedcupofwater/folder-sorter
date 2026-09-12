"""
Step 1: Static File Sorter
---------------------------
Scans ONE folder (once, not continuously) and moves files into
subfolders based on their extension.

This is not "watching" yet — that's step 2. Right now the goal is
to get the sorting logic itself solid.
"""

from pathlib import Path
import shutil
import time

# --- Configuration ---
# A dict mapping: destination folder name -> list of extensions that go there.
# Note: keys are just labels, the extensions inside are what actually matter.
EXTENSION_MAPS = {
    "Images": [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
    "ISOs": [".iso"],
    "Documents": [".pdf", ".docx", ".txt", ".xlsx", ".pptx"],
    "Installers": [".exe", ".msi", ".dmg", ".pkg", ".deb", ".appimage"],
}

IGNORED_EXTENSIONS: list[str] = [".crdownload", ".part", ".tmp"]

def build_extension_lookup(extension_map: dict) -> dict:
    """
    Flip the EXTENSION_MAP inside out so we can look up a folder by
    extension in O(1) instead of looping through every list every time.
    """
    lookup = {}
    for folder_name, extensions in extension_map.items():
        for ext in extensions:
            lookup[ext] = folder_name
    return lookup

def sort_folder(target_folder: Path, extension_map: dict) -> None:
    """Unchanged from before — still scans and moves files by extension."""
    lookup = build_extension_lookup(extension_map)

    for item in target_folder.iterdir():
        if not item.is_file():
            continue

        extension = item.suffix.lower()
        if extension in IGNORED_EXTENSIONS:
            continue

        destination_folder_name = lookup.get(extension)
        if destination_folder_name is None:
            continue

        destination_folder = target_folder / destination_folder_name
        destination_folder.mkdir(exist_ok=True)
        destination_path = destination_folder / item.name

        if not item.exists():
            continue  # another pass already moved this — nothing to do

        try:
            print(f"Moving: {item.name} -> {destination_folder_name}/")
            shutil.move(str(item), str(destination_path))
        except FileNotFoundError:
            print(f"Skipped {item.name} — already moved by another event.")

if __name__ == "__main__":
    downloads_folder = Path.home() / "sort_test"

    if not downloads_folder.exists():
        print(f"Folder not found: {downloads_folder}")
    else:
        try:
            while True:
                sort_folder(downloads_folder, EXTENSION_MAPS)
                print("Checking folder...")
                time.sleep(5)
        except KeyboardInterrupt:
            print("Stopped by user.")