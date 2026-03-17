import typer
from typing import Optional
import asyncio

from .main import TechNewsMultiAgentSystem

app = typer.Typer(help="Tech News Multi-Agent Analysis System")


@app.command()
def analyze(
    days: int = typer.Option(7, "--days", "-d", help="Number of days to look back"),
    verbose: bool = typer.Option(True, "--verbose", "-v", help="Show detailed output"),
):
    """Run a complete tech news analysis cycle"""
    
    async def run():
        system = TechNewsMultiAgentSystem()
        results = await system.run_analysis(max_age_days=days, verbose=verbose)
        if verbose:
            system.display_results(results)
        return results

    asyncio.run(run())


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query for technologies"),
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum results to show"),
):
    """Search for technologies in the memory"""
    
    async def run():
        system = TechNewsMultiAgentSystem()
        await system.search_technologies(query, limit=limit)

    asyncio.run(run())


@app.command()
def details(
    tech_name: str = typer.Argument(..., help="Name of the technology"),
):
    """Get detailed information about a specific technology"""
    
    async def run():
        system = TechNewsMultiAgentSystem()
        await system.get_technology_details(tech_name)

    asyncio.run(run())


@app.command()
def summary():
    """Generate a summary report of all tracked technologies"""
    
    async def run():
        system = TechNewsMultiAgentSystem()
        report = await system.generate_summary_report()
        print(report)

    asyncio.run(run())


@app.command()
def track(
    tech_name: str = typer.Argument(..., help="Name of the technology to track"),
):
    """Get development timeline for a specific technology"""
    
    async def run():
        system = TechNewsMultiAgentSystem()
        
        all_techs = await system.get_all_technologies()
        tech_id = None
        for tech in all_techs:
            if tech["name"].lower() == tech_name.lower():
                tech_id = tech["id"]
                break
        
        if tech_id:
            await system.dev_tracker.get_technology_timeline(tech_id)
        else:
            print(f"Technology '{tech_name}' not found in tracking system")

    asyncio.run(run())


@app.command()
def list(
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Filter by category"),
):
    """List all tracked technologies"""
    
    async def run():
        system = TechNewsMultiAgentSystem()
        all_techs = await system.get_all_technologies()
        
        if category:
            all_techs = [t for t in all_techs if t.get("category", "").lower() == category.lower()]
        
        from rich.console import Console
        from rich.table import Table
        from rich import box
        
        console = Console()
        table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
        table.add_column("Name", style="cyan")
        table.add_column("Category", style="green")
        table.add_column("Status", style="blue")
        table.add_column("Trend", style="yellow")
        table.add_column("Confidence", justify="right")
        table.add_column("Hype", justify="right")
        
        for tech in all_techs:
            table.add_row(
                tech.get("name", "N/A"),
                tech.get("category", "N/A"),
                tech.get("status", "N/A"),
                tech.get("trend_direction", "N/A"),
                f"{tech.get('confidence_score', 0):.2f}",
                f"{tech.get('hype_level', 0):.2f}",
            )
        console.print(table)

    asyncio.run(run())


if __name__ == "__main__":
    app()
