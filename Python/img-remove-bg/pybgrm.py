"""
Background removal tool using PIL/Pillow.

Removes white/whitish backgrounds from images by making them transparent.
"""

import os
from pathlib import Path
from typing import Optional
from PIL import Image
import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table

console = Console()
app = typer.Typer(
    name="pybgrm",
    help="[bold cyan]Background Removal Tool[/bold cyan]\n\nRemove white/whitish backgrounds from images by making them transparent.",
    rich_markup_mode="rich",
    add_completion=False,
)


def remove_background(
    input_path: str,
    output_path: str,
    threshold: int = 220,
) -> None:
    """
    Remove white/whitish background from an image.
    
    Args:
        input_path: Path to input image
        output_path: Path to save output image (must be PNG for transparency)
        threshold: RGB threshold for considering a pixel "white" (0-255)
    """
    try:
        # Open and convert to RGBA to support transparency
        img = Image.open(input_path).convert("RGBA")
        datas = img.getdata()

        new_data = []
        for item in datas:
            # Check for "whitish" pixels (all RGB channels above threshold)
            if item[0] > threshold and item[1] > threshold and item[2] > threshold:
                # Make pixel fully transparent
                new_data.append((255, 255, 255, 0))
            else:
                # Keep original pixel
                new_data.append(item)

        img.putdata(new_data)
        img.save(output_path, "PNG")
        console.print(f"[bold green]✅ Successfully removed background![/bold green]")
        console.print(f"[dim]Output saved to:[/dim] [cyan]{output_path}[/cyan]")
    except FileNotFoundError:
        console.print(f"[bold red]❌ Error:[/bold red] Input file not found: [yellow]{input_path}[/yellow]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]❌ Error processing image:[/bold red] {e}")
        raise typer.Exit(code=1)


def clean_path(path: str) -> str:
    """
    Clean a file path by removing surrounding quotes and whitespace.
    
    Args:
        path: Input path string that may have quotes
        
    Returns:
        Cleaned path string
    """
    if path:
        # Remove surrounding quotes (single or double) and whitespace
        path = path.strip().strip('"').strip("'")
    return path


def generate_output_path(input_path: str) -> str:
    """
    Generate output path from input path.
    
    Adds '_transparent' before the file extension.
    """
    input_file = Path(input_path)
    output_file = input_file.parent / f"{input_file.stem}_transparent{input_file.suffix}"
    # Always use PNG extension for transparency support
    return str(output_file.with_suffix('.png'))


def show_help_message():
    """Display a helpful message about the tool."""
    help_text = Text()
    help_text.append("Background Removal Tool\n", style="bold cyan")
    help_text.append("\nThis tool removes white/whitish backgrounds from images by making them transparent.\n", style="dim")
    
    help_text.append("\n[bold]Usage Examples:[/bold]\n", style="bold")
    help_text.append("  python pybgrm.py image.png\n", style="cyan")
    help_text.append("  python pybgrm.py image.png -o output.png\n", style="cyan")
    help_text.append("  python pybgrm.py image.png --threshold 200\n", style="cyan")
    
    help_text.append("\n[bold]Options:[/bold]\n", style="bold")
    help_text.append("  [yellow]-o, --output[/yellow]    Specify output file path (default: adds '_transparent' to input name)\n")
    help_text.append("  [yellow]-t, --threshold[/yellow] RGB threshold for white detection (0-255, default: 220)\n")
    help_text.append("  [yellow]--help[/yellow]          Show this help message\n")
    
    help_text.append("\n[bold]Note:[/bold] Output is always saved as PNG to support transparency.\n", style="dim")
    
    console.print(Panel(help_text, title="[bold]pybgrm[/bold]", border_style="cyan", padding=(1, 2)))


@app.command()
def main(
    input_path: Optional[str] = typer.Argument(
        None,
        help="[cyan]Path to input image file[/cyan]",
    ),
    output_path: Optional[str] = typer.Option(
        None,
        "-o",
        "--output",
        help="[yellow]Path to output image file[/yellow] (default: input_transparent.png)",
    ),
    threshold: int = typer.Option(
        220,
        "-t",
        "--threshold",
        help="[yellow]RGB threshold for white detection[/yellow] (0-255, default: 220). Higher values = more aggressive removal.",
        min=0,
        max=255,
    ),
):
    """
    [bold cyan]Remove white/whitish backgrounds from images.[/bold cyan]
    
    Makes pixels with RGB values above the threshold transparent.
    Output is always saved as PNG to support transparency.
    
    [bold]Examples:[/bold]
    
    \b
    • python pybgrm.py image.png
    • python pybgrm.py image.png -o output.png
    • python pybgrm.py image.png --threshold 200
    """
    # Show help message if no input provided, then prompt
    if input_path is None:
        show_help_message()
        console.print()  # Add spacing
        input_path = typer.prompt("[cyan]Enter input image path[/cyan]")
    
    # Clean the input path (remove quotes, whitespace)
    input_path = clean_path(input_path)
    
    # Validate input file exists
    if not os.path.exists(input_path):
        console.print(f"[bold red]❌ Error:[/bold red] Input file not found: [yellow]{input_path}[/yellow]")
        raise typer.Exit(code=1)
    
    # Generate output path if not provided
    if output_path is None:
        output_path = generate_output_path(input_path)
    else:
        # Clean output path as well
        output_path = clean_path(output_path)
    
    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    # Process the image
    remove_background(input_path, output_path, threshold)


if __name__ == "__main__":
    app()