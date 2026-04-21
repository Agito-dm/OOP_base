from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from src.day3.bank import Bank
from src.day4.model.transaction import Transaction, TransactionStatus
from src.day5.audit import AuditLog
from src.day5.risk import RiskAnalyzer, RiskLevel

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


@dataclass
class BalancePoint:
    timestamp: datetime
    value: float


class ReportBuilder:
    """
    ReportBuilder:
    - формирование текстовых, JSON и CSV отчётов
    - графики matplotlib
    """

    def __init__(
        self,
        bank: Bank,
        *,
        transactions: Optional[list[Transaction]] = None,
        audit_log: Optional[AuditLog] = None,
        risk_analyzer: Optional[RiskAnalyzer] = None,
        output_dir: str | Path = "docs/reports",
    ) -> None:
        self.bank = bank
        self.transactions = transactions or []
        self.audit = audit_log
        self.risk = risk_analyzer
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # series_id -> list[BalancePoint]
        self._balance_series: dict[str, list[BalancePoint]] = defaultdict(list)


    def add_account_balance_snapshot(self, account_id: str, *, timestamp: datetime | None = None) -> None:
        acc = self.bank.accounts.get(account_id)
        if not acc:
            return
        ts = timestamp or datetime.now()
        balance = float(acc.get_account_info()["balance"])
        self._balance_series[f"account:{account_id}"].append(BalancePoint(ts, balance))

    def add_client_balance_snapshot(self, client_id: str, *, timestamp: datetime | None = None) -> None:
        ts = timestamp or datetime.now()
        accounts = self.bank.search_accounts(client_id=client_id)
        total = sum(float(a.get_account_info()["balance"]) for a in accounts)
        self._balance_series[f"client:{client_id}"].append(BalancePoint(ts, float(total)))

    def add_bank_balance_snapshot(self, *, timestamp: datetime | None = None) -> None:
        ts = timestamp or datetime.now()
        total = float(self.bank.get_total_balance())
        self._balance_series["bank:total"].append(BalancePoint(ts, total))


    def build_bank_report(self, *, top_n: int = 3) -> dict[str, Any]:
        accounts = list(self.bank.accounts.values())
        clients = list(self.bank.clients.values())

        by_type = Counter(acc.__class__.__name__.lower() for acc in accounts)
        by_status = Counter(acc.status.value for acc in accounts)
        by_currency = Counter(acc.currency.value for acc in accounts)

        tx_status = Counter(tx.status.value for tx in self.transactions)
        completed_fees_total = sum(float(tx.fee) for tx in self.transactions if tx.status == TransactionStatus.COMPLETED)

        top_clients = self.bank.get_clients_ranking()[:top_n]

        suspicious_count = 0
        if self.risk:
            suspicious_count = len(self.risk.suspicious_operations(min_level=RiskLevel.MEDIUM))

        audit_error_stats = self.audit.error_stats() if self.audit else {}

        return {
            "generated_at": datetime.now().isoformat(),
            "bank": {
                "clients_count": len(clients),
                "accounts_count": len(accounts),
                "total_balance": float(self.bank.get_total_balance()),
                "accounts_by_type": dict(by_type),
                "accounts_by_status": dict(by_status),
                "accounts_by_currency": dict(by_currency),
                "top_clients": [{"client_id": cid, "total_balance": float(total)} for cid, total in top_clients],
                "bank_suspicious_events_count": len(self.bank.suspicious_events),
            },
            "transactions": {
                "count": len(self.transactions),
                "by_status": dict(tx_status),
                "completed_fees_total": float(completed_fees_total),
            },
            "risks": {
                "suspicious_count_medium_plus": suspicious_count,
            },
            "audit": {
                "error_stats": audit_error_stats,
                "events_count": len(self.audit.events) if self.audit else 0,
            },
        }

    def build_client_report(self, client_id: str, *, last_n_txs: int = 10) -> dict[str, Any]:
        client = self.bank.clients.get(client_id)
        if not client:
            return {"error": "client not found", "client_id": client_id}

        accounts = self.bank.search_accounts(client_id=client_id)
        account_ids = {a.id for a in accounts}

        related_txs = [
            tx for tx in self.transactions
            if tx.sender_account_id in account_ids or (tx.recipient_account_id in account_ids if tx.recipient_account_id else False)
        ]
        related_txs_sorted = sorted(related_txs, key=lambda t: t.created_at, reverse=True)
        tx_status = Counter(tx.status.value for tx in related_txs)

        total_balance = sum(float(a.get_account_info()["balance"]) for a in accounts)

        risk_profile = self.risk.client_risk_profile(client_id) if self.risk else None

        suspicious_related = []
        if self.risk:
            suspicious = self.risk.suspicious_operations(min_level=RiskLevel.MEDIUM)
            suspicious_ids = {r.tx_id for r in suspicious}
            suspicious_related = [tx.tx_id for tx in related_txs if tx.tx_id in suspicious_ids]

        return {
            "generated_at": datetime.now().isoformat(),
            "client": {
                "client_id": client_id,
                "full_name": client.full_name,
                "status": client.status.value,
                "contacts": client.contacts,
                "accounts": [
                    {
                        "id": a.id,
                        "type": a.__class__.__name__.lower(),
                        "status": a.status.value,
                        "balance": float(a.get_account_info()["balance"]),
                        "currency": a.currency.value,
                    }
                    for a in accounts
                ],
                "total_balance": float(total_balance),
            },
            "transactions": {
                "count": len(related_txs),
                "by_status": dict(tx_status),
                "last": [
                    {
                        "tx_id": tx.tx_id,
                        "type": tx.tx_type.value,
                        "amount": float(tx.amount),
                        "currency": tx.currency.value,
                        "status": tx.status.value,
                        "fee": float(tx.fee),
                        "created_at": tx.created_at.isoformat(),
                    }
                    for tx in related_txs_sorted[:last_n_txs]
                ],
            },
            "risk_profile": risk_profile,
            "suspicious_tx_ids_medium_plus": suspicious_related,
        }

    def build_risk_report(self, *, limit: int = 50) -> dict[str, Any]:
        if not self.risk:
            return {"generated_at": datetime.now().isoformat(), "risk": {"enabled": False}}

        counts = Counter(r.risk_level.value for r in self.risk.history)
        suspicious = self.risk.suspicious_operations(min_level=RiskLevel.MEDIUM)[:limit]

        # топ клиентов по числу high, medium
        score = Counter()
        for r in self.risk.history:
            if r.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH):
                score[r.client_id] += 1

        top_risky_clients = [{"client_id": cid, "suspicious_ops": int(cnt)} for cid, cnt in score.most_common(10)]

        return {
            "generated_at": datetime.now().isoformat(),
            "risk": {
                "enabled": True,
                "counts_by_level": dict(counts),
                "suspicious_operations": [
                    {
                        "timestamp": r.timestamp.isoformat(),
                        "client_id": r.client_id,
                        "tx_id": r.tx_id,
                        "risk_level": r.risk_level.value,
                        "findings": [f.code for f in r.findings],
                    }
                    for r in suspicious
                ],
                "top_risky_clients": top_risky_clients,
            },
        }


    def export_text(self, report: dict[str, Any], filename: str) -> Path:
        def fmt(value: Any, indent: int = 0) -> list[str]:
            pad = "  " * indent
            if isinstance(value, dict):
                lines = []
                for k, v in value.items():
                    if isinstance(v, (dict, list)):
                        lines.append(f"{pad}{k}:")
                        lines.extend(fmt(v, indent + 1))
                    else:
                        lines.append(f"{pad}{k}: {v}")
                return lines
            if isinstance(value, list):
                lines = []
                for item in value:
                    if isinstance(item, (dict, list)):
                        lines.append(f"{pad}-")
                        lines.extend(fmt(item, indent + 1))
                    else:
                        lines.append(f"{pad}- {item}")
                return lines
            return [f"{pad}{value}"]
        
        path = self.output_dir / filename
        text = "\n".join(fmt(report))
        path.write_text(text, encoding="utf-8")
        return path

    def export_to_json(self, report: dict[str, Any], filename: str) -> Path:
        path = self.output_dir / filename
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def export_to_csv(self, report_type: str, report: dict[str, Any]) -> list[Path]:
        """
        report_type: 'bank' | 'client' | 'risk'
        Сохраняет один или несколько CSV файлов.
        """
        written: list[Path] = []

        def write_rows(path: Path, header: list[str], rows: list[list[Any]]) -> None:
            with path.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(header)
                w.writerows(rows)

        if report_type == "bank":
            top = report["bank"]["top_clients"]
            p1 = self.output_dir / "bank_top_clients.csv"
            write_rows(p1, ["client_id", "total_balance"], [[r["client_id"], r["total_balance"]] for r in top])
            written.append(p1)

            by_status = report["transactions"]["by_status"]
            p2 = self.output_dir / "bank_tx_status.csv"
            write_rows(p2, ["status", "count"], [[k, v] for k, v in by_status.items()])
            written.append(p2)

            return written

        if report_type == "client":
            client = report["client"]
            accounts = client["accounts"]
            p1 = self.output_dir / f"client_{client['client_id']}_accounts.csv"
            write_rows(
                p1,
                ["account_id", "type", "status", "balance", "currency"],
                [[a["id"], a["type"], a["status"], a["balance"], a["currency"]] for a in accounts],
            )
            written.append(p1)

            last = report["transactions"]["last"]
            p2 = self.output_dir / f"client_{client['client_id']}_tx_last.csv"
            write_rows(
                p2,
                ["tx_id", "type", "amount", "currency", "status", "fee", "created_at"],
                [[t["tx_id"], t["type"], t["amount"], t["currency"], t["status"], t["fee"], t["created_at"]] for t in last],
            )
            written.append(p2)
            return written

        if report_type == "risk":
            if not report.get("risk", {}).get("enabled", False):
                return written

            ops = report["risk"]["suspicious_operations"]
            p1 = self.output_dir / "risk_suspicious_operations.csv"
            write_rows(
                p1,
                ["timestamp", "client_id", "tx_id", "risk_level", "findings"],
                [[o["timestamp"], o["client_id"], o["tx_id"], o["risk_level"], ";".join(o["findings"])] for o in ops],
            )
            written.append(p1)
            return written

        raise ValueError("Unknown report_type. Use: bank | client | risk")


    def save_charts(
        self,
        *,
        bank_report: dict[str, Any],
        risk_report: dict[str, Any] | None = None,
        balance_series_id: str | None = None,
    ) -> list[Path]:
        paths: list[Path] = []

        by_status = bank_report["transactions"]["by_status"]
        if by_status:
            fig = plt.figure()
            labels = list(by_status.keys())
            sizes = list(by_status.values())
            plt.pie(sizes, labels=labels, autopct="%1.1f%%")
            plt.title("Transaction statuses")
            p = self.output_dir / "chart_pie_tx_status.png"
            fig.savefig(p, dpi=150, bbox_inches="tight")
            plt.close(fig)
            paths.append(p)

        top = bank_report["bank"]["top_clients"]
        if top:
            fig = plt.figure()
            x = [r["client_id"] for r in top]
            y = [float(r["total_balance"]) for r in top]
            plt.bar(x, y)
            plt.title("Top clients by total balance")
            plt.xlabel("client_id")
            plt.ylabel("total_balance")
            p = self.output_dir / "chart_bar_top_clients.png"
            fig.savefig(p, dpi=150, bbox_inches="tight")
            plt.close(fig)
            paths.append(p)

        # выбор серии явно заданную, иначе bank:total, иначе любую первую
        series_id = balance_series_id
        if series_id is None:
            if self._balance_series.get("bank:total"):
                series_id = "bank:total"
            elif self._balance_series:
                series_id = next(iter(self._balance_series.keys()))

        if series_id and self._balance_series.get(series_id):
            points = sorted(self._balance_series[series_id], key=lambda p: p.timestamp)
            fig = plt.figure()
            xs = [p.timestamp for p in points]
            ys = [p.value for p in points]
            plt.plot(xs, ys)
            plt.title(f"Balance movement ({series_id})")
            plt.xlabel("time")
            plt.ylabel("balance")
            p = self.output_dir / f"chart_line_balance_{series_id.replace(':', '_')}.png"
            fig.savefig(p, dpi=150, bbox_inches="tight")
            plt.close(fig)
            paths.append(p)

        return paths
