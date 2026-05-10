import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

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
from .config.llm_config import LLMConfig


console = Console()

AGENT_META = {
    "NewsCollectorAgent": {
        "label": "News Collector",
        "icon": "[bold blue]📡[/bold blue]",
        "color": "blue",
    },
    "TechnologyAnalyzerAgent": {
        "label": "Technology Analyzer",
        "icon": "[bold cyan]🔬[/bold cyan]",
        "color": "cyan",
    },
    "MemoryManagerAgent": {
        "label": "Memory Manager",
        "icon": "[bold green]🧠[/bold green]",
        "color": "green",
    },
    "DevelopmentTrackerAgent": {
        "label": "Development Tracker",
        "icon": "[bold yellow]📈[/bold yellow]",
        "color": "yellow",
    },
    "ReportGeneratorAgent": {
        "label": "Report Generator",
        "icon": "[bold magenta]📄[/bold magenta]",
        "color": "magenta",
    },
}


class TechNewsMultiAgentSystem:
    def __init__(
        self,
        memory_dir: Optional[str] = None,
        sqlite_path: Optional[str] = None,
        report_dir: Optional[str] = None,
        use_llm: bool = True,
        verbose: bool = False,
    ):
        self.memory_dir = memory_dir or "./memory_db"
        self.sqlite_path = sqlite_path or "./data/news_content.db"
        self.report_dir = report_dir or "./reports"
        self.use_llm = use_llm
        self.verbose = verbose

        if verbose:
            self._setup_verbose_logging()

        # Initialize storage
        self.memory = VectorMemory(persist_directory=self.memory_dir)
        self.sqlite_store = SQLiteStore(db_path=self.sqlite_path)

        # Initialize orchestrator
        self.orchestrator = AgentOrchestrator(memory=self.memory)

        # Initialize agents with SQLite store
        self.news_collector = NewsCollectorAgent(
            memory=self.memory, sqlite_store=self.sqlite_store
        )
        self.tech_analyzer = TechnologyAnalyzerAgent(memory=self.memory)
        self.memory_manager = MemoryManagerAgent(memory=self.memory)
        self.dev_tracker = DevelopmentTrackerAgent(memory=self.memory)
        self.report_generator = ReportGeneratorAgent(
            sqlite_store=self.sqlite_store,
            report_dir=self.report_dir,
            use_llm=self.use_llm,
        )

        self._check_llm_connectivity()

        self._register_agents()

    def _register_agents(self):
        self.orchestrator.register_agent(self.news_collector)
        self.orchestrator.register_agent(self.tech_analyzer)
        self.orchestrator.register_agent(self.memory_manager)
        self.orchestrator.register_agent(self.dev_tracker)
        self.orchestrator.register_agent(self.report_generator)

    def _setup_verbose_logging(self):
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("    ⏱️  %(message)s"))
        for logger_name in [
            "src.utils.llm_analyzer",
            "src.utils.rss_fetcher",
            "src.utils.content_extractor",
            "src.utils.entity_extractor",
        ]:
            lg = logging.getLogger(logger_name)
            lg.setLevel(logging.INFO)
            if not any(isinstance(h, logging.StreamHandler) for h in lg.handlers):
                lg.addHandler(handler)
            lg.propagate = False

    def _check_llm_connectivity(self):
        base_url = LLMConfig.get_base_url()
        model = LLMConfig.get_model("news_collector")

        if not base_url:
            console.print("[dim]ℹ[/dim] LLM disabled (set LLM_BASE_URL to enable)")
            return

        from .utils.llm_analyzer import LLMAnalyzer
        from langchain_core.output_parsers import StrOutputParser
        import asyncio
        import threading

        try:
            llm_kwargs = LLMConfig.create_llm_kwargs("news_collector")
            llm = LLMAnalyzer(**llm_kwargs, verbose=False)
            chain = llm._get_llm() | StrOutputParser()

            async def send_test():
                return await chain.ainvoke("Is LLM sentient? Answer in one sentence.")

            def run_in_thread():
                return asyncio.run(send_test())

            result = [None]

            def run_in_thread():
                result[0] = asyncio.run(send_test())

            t = threading.Thread(target=run_in_thread)
            t.start()
            t.join(timeout=60)
            if t.is_alive():
                console.print(f"[yellow]⚠[/yellow] LLM connection timed out")
            else:
                response = result[0]
                console.print(
                    f'[green]✓[/green] LLM connected: model={model} — "{response[:80]}{"..." if len(response) > 80 else ""}"'
                )
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] LLM connection failed: {str(e)[:100]}")

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

        period_end = datetime.now()
        period_start = period_end - timedelta(days=max_age_days)

        thread_results = {}
        step_timings = {}

        # ── Step 1/5: News Collector ──────────────────────────────────
        if verbose:
            meta = AGENT_META["NewsCollectorAgent"]
            console.print(
                f"\n{meta['icon']} [bold]Step 1/5:[/bold] {meta['label']} — Collecting news articles..."
            )

        self.news_collector.verbose = verbose
        if self.news_collector.llm_analyzer:
            self.news_collector.llm_analyzer.verbose = verbose
            if verbose:
                console.print("    [dim]⏱️  LLM timing enabled for news collector[/dim]")

        t0 = time.monotonic()
        news_mentions = await self.news_collector.process(
            {"max_age_days": max_age_days, "sources": sources}
        )
        step_timings["NewsCollectorAgent"] = time.monotonic() - t0

        article_count = self.sqlite_store.get_article_count()
        thread_results["NewsCollectorAgent"] = {
            "articles_collected": len(news_mentions),
            "total_articles_in_db": article_count,
            "duration_s": round(step_timings["NewsCollectorAgent"], 2),
        }

        if verbose:
            meta = AGENT_META["NewsCollectorAgent"]
            console.print(
                f"{meta['icon']} [green]✓[/green] {meta['label']}: "
                f"{thread_results['NewsCollectorAgent']['articles_collected']} tech articles collected "
                f"({thread_results['NewsCollectorAgent']['total_articles_in_db']} total in DB) "
                f"[dim]({step_timings['NewsCollectorAgent']:.1f}s)[/dim]"
            )

        # ── Step 2/5: Technology Analyzer ─────────────────────────────
        if verbose:
            meta = AGENT_META["TechnologyAnalyzerAgent"]
            console.print(
                f"\n{meta['icon']} [bold]Step 2/5:[/bold] {meta['label']} — Analyzing technologies..."
            )

        existing_techs = self.memory.get_all_technologies()

        t0 = time.monotonic()
        analysis_result = await self.tech_analyzer.process(
            {
                "mentions": [m.model_dump(mode="json") for m in news_mentions],
                "existing_technologies": existing_techs,
            }
        )
        step_timings["TechnologyAnalyzerAgent"] = time.monotonic() - t0

        thread_results["TechnologyAnalyzerAgent"] = {
            "new_technologies_count": len(analysis_result["new_technologies"]),
            "updated_technologies_count": len(analysis_result["updated_technologies"]),
            "promising_technologies_count": len(
                analysis_result["promising_technologies"]
            ),
            "total_mentions_analyzed": analysis_result.get(
                "total_mentions_analyzed", 0
            ),
            "duration_s": round(step_timings["TechnologyAnalyzerAgent"], 2),
        }

        if verbose:
            meta = AGENT_META["TechnologyAnalyzerAgent"]
            console.print(
                f"{meta['icon']} [green]✓[/green] {meta['label']}: "
                f"{thread_results['TechnologyAnalyzerAgent']['new_technologies_count']} new, "
                f"{thread_results['TechnologyAnalyzerAgent']['updated_technologies_count']} updated, "
                f"{thread_results['TechnologyAnalyzerAgent']['promising_technologies_count']} promising "
                f"[dim]({step_timings['TechnologyAnalyzerAgent']:.1f}s)[/dim]"
            )

        # ── Step 3/5: Memory Manager ──────────────────────────────────
        if verbose:
            meta = AGENT_META["MemoryManagerAgent"]
            console.print(
                f"\n{meta['icon']} [bold]Step 3/5:[/bold] {meta['label']} — Storing in memory..."
            )

        t0 = time.monotonic()
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
        step_timings["MemoryManagerAgent"] = time.monotonic() - t0

        thread_results["MemoryManagerAgent"] = {
            "new_stored": memory_result["new_technologies_stored"],
            "updated_stored": memory_result["updated_technologies_stored"],
            "duration_s": round(step_timings["MemoryManagerAgent"], 2),
        }

        if verbose:
            meta = AGENT_META["MemoryManagerAgent"]
            console.print(
                f"{meta['icon']} [green]✓[/green] {meta['label']}: "
                f"{thread_results['MemoryManagerAgent']['new_stored']} new, "
                f"{thread_results['MemoryManagerAgent']['updated_stored']} updated technologies stored "
                f"[dim]({step_timings['MemoryManagerAgent']:.1f}s)[/dim]"
            )

        # ── Step 4/5: Development Tracker ──────────────────────────────
        if verbose:
            meta = AGENT_META["DevelopmentTrackerAgent"]
            console.print(
                f"\n{meta['icon']} [bold]Step 4/5:[/bold] {meta['label']} — Tracking developments..."
            )

        t0 = time.monotonic()
        tracking_result = await self.dev_tracker.process(
            {"memory_update": memory_result}
        )
        step_timings["DevelopmentTrackerAgent"] = time.monotonic() - t0

        thread_results["DevelopmentTrackerAgent"] = {
            "reports_generated": tracking_result["reports_generated"],
            "promising_count": len(tracking_result["promising_technologies"]),
            "significant_developments": tracking_result[
                "significant_developments_count"
            ],
            "status_changes_recommended": len(
                tracking_result.get("status_changes_recommended", [])
            ),
            "duration_s": round(step_timings["DevelopmentTrackerAgent"], 2),
        }

        if verbose:
            meta = AGENT_META["DevelopmentTrackerAgent"]
            console.print(
                f"{meta['icon']} [green]✓[/green] {meta['label']}: "
                f"{thread_results['DevelopmentTrackerAgent']['reports_generated']} reports, "
                f"{thread_results['DevelopmentTrackerAgent']['promising_count']} high-potential technologies, "
                f"{thread_results['DevelopmentTrackerAgent']['significant_developments']} significant developments "
                f"[dim]({step_timings['DevelopmentTrackerAgent']:.1f}s)[/dim]"
            )

        # ── Step 5/5: Report Generator ────────────────────────────────
        report = None
        if generate_report:
            if verbose:
                meta = AGENT_META["ReportGeneratorAgent"]
                console.print(
                    f"\n{meta['icon']} [bold]Step 5/5:[/bold] {meta['label']} — Generating report..."
                )

            self.report_generator.verbose = verbose
            if self.report_generator.llm_analyzer:
                self.report_generator.llm_analyzer.verbose = verbose
                if verbose:
                    console.print(
                        "    [dim]⏱️  LLM timing enabled for report generator[/dim]"
                    )

            all_technologies = (
                analysis_result["new_technologies"]
                + analysis_result["updated_technologies"]
            )

            t0 = time.monotonic()
            report = await self.report_generator.process(
                {
                    "period_start": period_start,
                    "period_end": period_end,
                    "technologies": [
                        t.model_dump(mode="json") for t in all_technologies
                    ],
                    "developments": tracking_result,
                }
            )
            step_timings["ReportGeneratorAgent"] = time.monotonic() - t0

            thread_results["ReportGeneratorAgent"] = {
                "report_id": report.id,
                "report_file": report.file_path,
                "articles_analyzed": report.significance_analysis.get(
                    "total_articles", 0
                ),
                "duration_s": round(step_timings["ReportGeneratorAgent"], 2),
            }

            if verbose:
                meta = AGENT_META["ReportGeneratorAgent"]
                console.print(
                    f"{meta['icon']} [green]✓[/green] {meta['label']}: "
                    f"Report {report.id} generated "
                    f"[dim]({step_timings['ReportGeneratorAgent']:.1f}s)[/dim]"
                )

        total_duration = sum(step_timings.values())

        return {
            "news_collected": len(news_mentions),
            "new_technologies": analysis_result["new_technologies"],
            "updated_technologies": analysis_result["updated_technologies"],
            "promising_technologies": analysis_result["promising_technologies"],
            "memory_result": memory_result,
            "tracking_result": tracking_result,
            "report": report,
            "thread_results": thread_results,
            "step_timings": step_timings,
            "total_duration": round(total_duration, 2),
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

        # ── Thread / Agent Summary Table ──────────────────────────────
        thread_results = results.get("thread_results", {})
        step_timings = results.get("step_timings", {})
        if thread_results:
            console.print("\n[bold yellow]Agent Pipeline Results:[/bold yellow]")
            thread_table = Table(
                show_header=True,
                header_style="bold magenta",
                box=box.ROUNDED,
                title="Thread Results",
            )
            thread_table.add_column("Agent", style="bold", min_width=26)
            thread_table.add_column("Key Metrics", style="cyan", min_width=40)
            thread_table.add_column("Duration", justify="right", style="green")

            for agent_name, meta in AGENT_META.items():
                if agent_name not in thread_results:
                    continue
                tr = thread_results[agent_name]
                duration = tr.get("duration_s", step_timings.get(agent_name, 0))

                if agent_name == "NewsCollectorAgent":
                    metrics = (
                        f"{tr.get('articles_collected', 0)} articles collected, "
                        f"{tr.get('total_articles_in_db', 0)} total in DB"
                    )
                elif agent_name == "TechnologyAnalyzerAgent":
                    metrics = (
                        f"{tr.get('new_technologies_count', 0)} new, "
                        f"{tr.get('updated_technologies_count', 0)} updated, "
                        f"{tr.get('promising_technologies_count', 0)} promising"
                    )
                elif agent_name == "MemoryManagerAgent":
                    metrics = (
                        f"{tr.get('new_stored', 0)} new stored, "
                        f"{tr.get('updated_stored', 0)} updated stored"
                    )
                elif agent_name == "DevelopmentTrackerAgent":
                    metrics = (
                        f"{tr.get('reports_generated', 0)} reports, "
                        f"{tr.get('promising_count', 0)} promising, "
                        f"{tr.get('significant_developments', 0)} significant dev"
                    )
                elif agent_name == "ReportGeneratorAgent":
                    metrics = (
                        f"Report {tr.get('report_id', 'N/A')[:8]}..., "
                        f"{tr.get('articles_analyzed', 0)} articles analyzed"
                    )
                else:
                    metrics = str(tr)

                thread_table.add_row(
                    f"{meta['icon']} {meta['label']}",
                    metrics,
                    f"{duration:.1f}s",
                )

            total_duration = results.get("total_duration", sum(step_timings.values()))
            thread_table.add_row(
                "[bold]Total[/bold]",
                "",
                f"[bold]{total_duration:.1f}s[/bold]",
            )
            console.print(thread_table)

        # ── News Collector Thread ──────────────────────────────────────
        nc = thread_results.get("NewsCollectorAgent", {})
        if nc:
            console.print(
                f"\n{AGENT_META['NewsCollectorAgent']['icon']} "
                f"[bold]{AGENT_META['NewsCollectorAgent']['label']}[/bold] — "
                f"{nc.get('articles_collected', 0)} tech articles collected "
                f"({nc.get('total_articles_in_db', 0)} total in DB)"
            )

        # ── Technology Analyzer Thread ─────────────────────────────────
        if results["new_technologies"]:
            console.print(
                f"\n{AGENT_META['TechnologyAnalyzerAgent']['icon']} "
                f"[bold]{AGENT_META['TechnologyAnalyzerAgent']['label']}[/bold] — "
                f"New Technologies Detected:"
            )
            table = Table(
                show_header=True, header_style="bold magenta", box=box.ROUNDED
            )
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
            console.print(
                f"\n{AGENT_META['TechnologyAnalyzerAgent']['icon']} "
                f"[bold]{AGENT_META['TechnologyAnalyzerAgent']['label']}[/bold] — "
                f"Most Promising Technologies:"
            )
            table = Table(
                show_header=True, header_style="bold magenta", box=box.ROUNDED
            )
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

        # ── Development Tracker Thread ─────────────────────────────────
        if results["updated_technologies"]:
            dt = thread_results.get("DevelopmentTrackerAgent", {})
            console.print(
                f"\n{AGENT_META['DevelopmentTrackerAgent']['icon']} "
                f"[bold]{AGENT_META['DevelopmentTrackerAgent']['label']}[/bold] — "
                f"{len(results['updated_technologies'])} technologies with new developments"
            )

            tree = Tree("📊 Development Updates")
            for tech in results["updated_technologies"][:5]:
                branch = tree.add(f"[cyan]{tech.name}[/cyan]")
                if tech.key_developments:
                    for dev in tech.key_developments[:3]:
                        branch.add(f"[green]•[/green] {dev}")
            console.print(tree)

            sig_count = dt.get("significant_developments", 0)
            status_changes = dt.get("status_changes_recommended", 0)
            if sig_count or status_changes:
                console.print(
                    f"    Significant developments: {sig_count} | "
                    f"Status changes recommended: {status_changes}"
                )

        # ── Report Generator Thread ────────────────────────────────────
        if results.get("report"):
            report = results["report"]
            rg = thread_results.get("ReportGeneratorAgent", {})
            console.print(
                f"\n{AGENT_META['ReportGeneratorAgent']['icon']} "
                f"[bold]{AGENT_META['ReportGeneratorAgent']['label']}[/bold]"
            )
            console.print(
                Panel(
                    f"[bold]Report Generated[/bold]\n"
                    f"File: {report.file_path}\n"
                    f"ID: {report.id}\n"
                    f"Articles Analyzed: {report.significance_analysis.get('total_articles', 0)}\n"
                    f"Duration: {rg.get('duration_s', 0):.1f}s",
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
        console.print(f"[bold]Trend:[/bold] {tech_data.get('trend_direction', 'N/A')}")
        console.print(
            f"[bold]Confidence:[/bold] {tech_data.get('confidence_score', 0):.2f}"
        )
        console.print(f"[bold]Hype Level:[/bold] {tech_data.get('hype_level', 0):.2f}")

        if history["developments"]:
            console.print(
                f"\n[bold]Key Developments ({len(history['developments'])}):[/bold]"
            )
            for dev in history["developments"][:10]:
                console.print(f"  • {dev.get('development', 'N/A')}")

        if history["mentions"]:
            console.print(f"\n[bold]Recent News ({len(history['mentions'])}):[/bold]")
            for mention in history["mentions"][:5]:
                console.print(
                    f"  • {mention.get('title', 'N/A')} "
                    f"[dim]({mention.get('source', 'N/A')})[/dim]"
                )

        if history["similar_technologies"]:
            console.print(f"\n[bold]Similar Technologies:[/bold]")
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

        trending = [t for t in all_techs if t.get("trend_direction") == "rising"]
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
                    f"  • {tech.get('name', 'N/A')}: {tech.get('hype_level', 0):.2f}"
                )
            report.append("")

        report.append("=" * 60)
        return "\n".join(report)


async def main():
    system = TechNewsMultiAgentSystem(verbose=True)

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
