import os
import sys

def safe_rename_files(dry_run=False):
    """
    Safely rename files with numeric extensions to 'archive.7z.XXX' format.
    
    Args:
        dry_run (bool): If True, shows what would be renamed without making changes
    """
    files_to_rename = []
    
    # Find files matching criteria (numeric extensions, are actual files, not directories)
    for f in os.listdir('.'):
        if not os.path.isfile(f):  # Skip directories
            continue
        # Check if extension (after last dot) is numeric
        if not f.split('.')[-1].isdigit():
            continue
        files_to_rename.append(f)
    
    if not files_to_rename:
        print("No files with numeric extensions found.")
        return
    
    # Show what will be renamed
    print(f"Found {len(files_to_rename)} file(s) to rename:")
    for f in sorted(files_to_rename):
        new_name = f"archive.7z.{f.split('.')[-1]}"
        print(f"  {f} → {new_name}")
    
    if dry_run:
        print("\n(Dry-run mode - no files were renamed)")
        return
    
    # Confirm before proceeding
    response = input("\nProceed with renaming? (yes/no): ").strip().lower()
    if response != 'yes':
        print("Cancelled.")
        return
    
    # Perform renames with error handling
    failed = []
    for f in files_to_rename:
        try:
            new_name = f"archive.7z.{f.split('.')[-1]}"
            
            # Check if target already exists
            if os.path.exists(new_name):
                print(f"⚠ Skipped {f}: target {new_name} already exists")
                failed.append(f)
                continue
            
            os.rename(f, new_name)
            print(f"✓ Renamed: {f}")
        except Exception as e:
            print(f"✗ Error renaming {f}: {e}")
            failed.append(f)
    
    if failed:
        print(f"\n⚠ {len(failed)} file(s) failed to rename")
        sys.exit(1)
    else:
        print(f"\n✓ Successfully renamed {len(files_to_rename)} file(s)")

if __name__ == "__main__":
    # Run with --dry-run flag to preview changes without making them
    dry_run = "--dry-run" in sys.argv
    safe_rename_files(dry_run=dry_run)