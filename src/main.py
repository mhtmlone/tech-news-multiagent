import asyncio
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree
from rich import box

from .memory.vector_store import VectorMemory
from .storage.sqlite_store import SQLiteStore
from .agents.news_collector import NewsCollectorAgent
from .agents.technology_analyzer import TechnologyAnalyzerAgent
from .agents.memory_manager import MemoryManagerAgent
from .agents.development_tracker import DevelopmentTrackerAgent
from .agents.report_generator import ReportGeneratorAgent
from .agents.base import AgentOrchestrator


console = Console()


class TechNewsMultiAgentSystem:
    def __init__(
        self, 
        memory_dir: Optional[str] = None,
        sqlite_path: Optional[str] = None,
        report_dir: Optional[str] = None,
        use_llm: bool = True
    ):
        self.memory_dir = memory_dir or "./memory_db"
        self.sqlite_path = sqlite_path or "./data/news_content.db"
        self.report_dir = report_dir or "./reports"
        self.use_llm = use_llm
        
        # Initialize storage
        self.memory = VectorMemory(persist_directory=self.memory_dir)
        self.sqlite_store = SQLiteStore(db_path=self.sqlite_path)
        
        # Initialize orchestrator
        self.orchestrator = AgentOrchestrator(memory=self.memory)

        # Initialize agents with SQLite store
        self.news_collector = NewsCollectorAgent(
            memory=self.memory,
            sqlite_store=self.sqlite_store
        )
        self.tech_analyzer = TechnologyAnalyzerAgent(memory=self.memory)
        self.memory_manager = MemoryManagerAgent(memory=self.memory)
        self.dev_tracker = DevelopmentTrackerAgent(memory=self.memory)
        self.report_generator = ReportGeneratorAgent(
            sqlite_store=self.sqlite_store,
            report_dir=self.report_dir,
            use_llm=self.use_llm
        )

        self._register_agents()

    def _register_agents(self):
        self.orchestrator.register_agent(self.news_collector)
        self.orchestrator.register_agent(self.tech_analyzer)
        self.orchestrator.register_agent(self.memory_manager)
        self.orchestrator.register_agent(self.dev_tracker)
        self.orchestrator.register_agent(self.report_generator)

    async def run_analysis(
        self,
        max_age_days: int = 7,
        sources: Optional[list[str]] = None,
        verbose: bool = True,
        generate_report: bool = True,
    ) -> dict:
        if verbose:
            console.print(
                Panel(
                    "[bold blue]Starting Tech News Analysis[/bold blue]\n"
                    f"Analyzing news from the last {max_age_days} days",
                    title="Multi-Agent System",
                    box=box.ROUNDED,
                )
            )

        # Calculate period dates
        period_end = datetime.now()
        period_start = period_end - timedelta(days=max_age_days)

        if verbose:
            console.print("\n[bold]Step 1/5:[/bold] Collecting news articles...")
        news_mentions = await self.news_collector.process(
            {"max_age_days": max_age_days, "sources": sources}
        )
        if verbose:
            console.print(
                f"[green]✓[/green] Collected {len(news_mentions)} technology-related articles"
            )
            # Show SQLite storage info
            article_count = self.sqlite_store.get_article_count()
            console.print(
                f"[green]✓[/green] Stored in SQLite database ({article_count} total articles)"
            )

        if verbose:
            console.print("\n[bold]Step 2/5:[/bold] Analyzing technologies...")
        existing_techs = self.memory.get_all_technologies()
        analysis_result = await self.tech_analyzer.process(
            {
                "mentions": [m.model_dump(mode="json") for m in news_mentions],
                "existing_technologies": existing_techs,
            }
        )
        if verbose:
            console.print(
                f"[green]✓[/green] Identified {len(analysis_result['new_technologies'])} new technologies"
            )
            console.print(
                f"[green]✓[/green] Updated {len(analysis_result['updated_technologies'])} existing technologies"
            )
            console.print(
                f"[green]✓[/green] Found {len(analysis_result['promising_technologies'])} promising technologies"
            )

        if verbose:
            console.print("\n[bold]Step 3/5:[/bold] Storing in memory...")
        memory_result = await self.memory_manager.process(
            {
                "new_technologies": [
                    t.model_dump(mode="json")
                    for t in analysis_result["new_technologies"]
                ],
                "updated_technologies": [
                    t.model_dump(mode="json")
                    for t in analysis_result["updated_technologies"]
                ],
            }
        )
        if verbose:
            console.print(
                f"[green]✓[/green] Stored {memory_result['new_technologies_stored']} new and "
                f"{memory_result['updated_technologies_stored']} updated technologies"
            )

        if verbose:
            console.print("\n[bold]Step 4/5:[/bold] Tracking developments...")
        tracking_result = await self.dev_tracker.process(
            {"memory_update": memory_result}
        )
        if verbose:
            console.print(
                f"[green]✓[/green] Generated {tracking_result['reports_generated']} development reports"
            )
            console.print(
                f"[green]✓[/green] Identified {len(tracking_result['promising_technologies'])} "
                "high-potential technologies"
            )

        # Generate report
        report = None
        if generate_report:
            if verbose:
                console.print("\n[bold]Step 5/5:[/bold] Generating report...")
            
            all_technologies = (
                analysis_result["new_technologies"] + 
                analysis_result["updated_technologies"]
            )
            
            report = await self.report_generator.process({
                "period_start": period_start,
                "period_end": period_end,
                "technologies": [t.model_dump(mode="json") for t in all_technologies],
                "developments": tracking_result,
            })
            
            if verbose:
                console.print(
                    f"[green]✓[/green] Generated report: {report.file_path}"
                )
                console.print(
                    f"[green]✓[/green] Report ID: {report.id}"
                )

        return {
            "news_collected": len(news_mentions),
            "new_technologies": analysis_result["new_technologies"],
            "updated_technologies": analysis_result["updated_technologies"],
            "promising_technologies": analysis_result["promising_technologies"],
            "memory_result": memory_result,
            "tracking_result": tracking_result,
            "report": report,
            "timestamp": datetime.now().isoformat(),
        }

    def display_results(self, results: dict):
        console.print("\n")
        console.print(
            Panel(
                "[bold green]Analysis Complete![/bold green]",
                title="Results Summary",
                box=box.ROUNDED,
            )
        )

        if results["new_technologies"]:
            console.print("\n[bold yellow]New Technologies Detected:[/bold yellow]")
            table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
            table.add_column("Name", style="cyan")
            table.add_column("Category", style="green")
            table.add_column("Confidence", justify="right")
            table.add_column("Hype Level", justify="right")

            for tech in results["new_technologies"]:
                table.add_row(
                    tech.name,
                    tech.category,
                    f"{tech.confidence_score:.2f}",
                    f"{tech.hype_level:.2f}",
                )
            console.print(table)

        if results["promising_technologies"]:
            console.print("\n[bold yellow]Most Promising Technologies:[/bold yellow]")
            table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
            table.add_column("Name", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Trend", style="blue")
            table.add_column("Score", justify="right")

            for tech in results["promising_technologies"][:10]:
                table.add_row(
                    tech.name,
                    tech.status.value if hasattr(tech.status, "value") else tech.status,
                    tech.trend_direction,
                    f"{tech.confidence_score:.2f}",
                )
            console.print(table)

        if results["updated_technologies"]:
            console.print(
                f"\n[bold yellow]Updated Technologies:[/bold yellow] "
                f"{len(results['updated_technologies'])} technologies with new developments"
            )

            tree = Tree("📊 Development Updates")
            for tech in results["updated_technologies"][:5]:
                branch = tree.add(f"[cyan]{tech.name}[/cyan]")
                if tech.key_developments:
                    for dev in tech.key_developments[:3]:
                        branch.add(f"[green]•[/green] {dev}")
            console.print(tree)
        
        # Display report info if available
        if results.get("report"):
            report = results["report"]
            console.print(
                Panel(
                    f"[bold]Report Generated[/bold]\n"
                    f"File: {report.file_path}\n"
                    f"ID: {report.id}\n"
                    f"Articles Analyzed: {report.significance_analysis.get('total_articles', 0)}",
                    title="📄 Report",
                    box=box.ROUNDED,
                )
            )

    async def search_technologies(self, query: str, limit: int = 10):
        results = self.memory.search_technologies(query, n_results=limit)
        if not results:
            console.print(f"[yellow]No technologies found matching '{query}'[/yellow]")
            return []

        console.print(f"\n[bold]Found {len(results)} technologies:[/bold]")
        table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
        table.add_column("Name", style="cyan")
        table.add_column("Category", style="green")
        table.add_column("Status", style="blue")
        table.add_column("Trend", style="yellow")
        table.add_column("Confidence", justify="right")

        for tech in results:
            table.add_row(
                tech.get("name", "N/A"),
                tech.get("category", "N/A"),
                tech.get("status", "N/A"),
                tech.get("trend_direction", "N/A"),
                f"{tech.get('confidence_score', 0):.2f}",
            )
        console.print(table)
        return results

    async def get_technology_details(self, tech_name: str):
        history = await self.memory_manager.retrieve_technology_history(tech_name)
        if not history["found"]:
            console.print(f"[red]Technology '{tech_name}' not found[/red]")
            return None

        console.print(f"\n[bold cyan]{tech_name} - Detailed Report[/bold cyan]")

        tech_data = history["technology"]
        console.print(f"\n[bold]Category:[/bold] {tech_data.get('category', 'N/A')}")
        console.print(f"[bold]Status:[/bold] {tech_data.get('status', 'N/A')}")
        console.print(
            f"[bold]Trend:[/bold] {tech_data.get('trend_direction', 'N/A')}"
        )
        console.print(
            f"[bold]Confidence:[/bold] {tech_data.get('confidence_score', 0):.2f}"
        )
        console.print(
            f"[bold]Hype Level:[/bold] {tech_data.get('hype_level', 0):.2f}"
        )

        if history["developments"]:
            console.print(f"\n[bold]Key Developments ({len(history['developments'])}):[/bold]")
            for dev in history["developments"][:10]:
                console.print(f"  • {dev.get('development', 'N/A')}")

        if history["mentions"]:
            console.print(
                f"\n[bold]Recent News ({len(history['mentions'])}):[/bold]"
            )
            for mention in history["mentions"][:5]:
                console.print(
                    f"  • {mention.get('title', 'N/A')} "
                    f"[dim]({mention.get('source', 'N/A')})[/dim]"
                )

        if history["similar_technologies"]:
            console.print(
                f"\n[bold]Similar Technologies:[/bold]"
            )
            for similar in history["similar_technologies"]:
                console.print(
                    f"  • {similar.get('name', 'N/A')} "
                    f"[dim](similarity: {similar.get('similarity', 0):.2f})[/dim]"
                )

        return history

    async def get_all_technologies(self):
        return self.memory.get_all_technologies()

    async def generate_summary_report(self) -> str:
        all_techs = self.memory.get_all_technologies()

        by_category: dict[str, list] = {}
        for tech in all_techs:
            category = tech.get("category", "Other")
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(tech)

        report = []
        report.append("=" * 60)
        report.append("TECHNOLOGY TRACKING SUMMARY REPORT")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 60)
        report.append("")

        report.append(f"Total Technologies Tracked: {len(all_techs)}")
        report.append("")

        report.append("By Category:")
        for category, techs in sorted(by_category.items()):
            report.append(f"  {category}: {len(techs)}")
        report.append("")

        status_counts: dict[str, int] = {}
        for tech in all_techs:
            status = tech.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        report.append("By Status:")
        for status, count in sorted(status_counts.items()):
            report.append(f"  {status}: {count}")
        report.append("")

        trending = [
            t for t in all_techs if t.get("trend_direction") == "rising"
        ]
        if trending:
            report.append("Trending Technologies:")
            for tech in trending[:10]:
                report.append(
                    f"  • {tech.get('name', 'N/A')} ({tech.get('category', 'N/A')})"
                )
            report.append("")

        high_hype = sorted(
            all_techs, key=lambda x: x.get("hype_level", 0), reverse=True
        )[:5]
        if high_hype:
            report.append("Highest Hype Level:")
            for tech in high_hype:
                report.append(
                    f"  • {tech.get('name', 'N/A')}: "
                    f"{tech.get('hype_level', 0):.2f}"
                )
            report.append("")

        report.append("=" * 60)
        return "\n".join(report)


async def main():
    system = TechNewsMultiAgentSystem()

    console.print(
        Panel(
            "[bold]Tech News Multi-Agent Analysis System[/bold]\n"
            "AI-powered technology tracking and analysis",
            title="Welcome",
            box=box.ROUNDED,
        )
    )

    results = await system.run_analysis(max_age_days=7, verbose=True)
    system.display_results(results)

    return results


if __name__ == "__main__":
    asyncio.run(main())
