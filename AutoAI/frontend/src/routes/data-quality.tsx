import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import {
  ShieldCheck,
  AlertTriangle,
  AlertOctagon,
  Info,
  CheckCircle2,
  RefreshCw,
  Search,
  Filter,
  Layers,
  Database,
  BarChart3,
  Calendar,
  Zap,
  Clock,
  ArrowRight,
  ExternalLink,
} from "lucide-react";
import api, { type DataQualityReport, type DataQualityIssue, type DataQualityIssuesResponse } from "@/services/api";

export const Route = createFileRoute("/data-quality")({
  component: DataQualityPage,
});

export function DataQualityPage() {
  const [dataset, setDataset] = useState<"new_launches" | "catalog">("new_launches");
  const [report, setReport] = useState<DataQualityReport | null>(null);
  const [issuesData, setIssuesData] = useState<DataQualityIssuesResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Issues filters
  const [severityFilter, setSeverityFilter] = useState<string>("");
  const [fieldFilter, setFieldFilter] = useState<string>("");
  const [search, setSearch] = useState<string>("");
  const [page, setPage] = useState<number>(1);

  const fetchData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      // 1. Fetch Summary Report
      const reportRes = await api.get<DataQualityReport>("/data-quality/report", {
        params: { dataset },
      });
      setReport(reportRes.data);

      // 2. Fetch Issues List
      const params: Record<string, any> = {
        dataset,
        page,
        page_size: 50,
      };
      if (severityFilter) params.severity = severityFilter;
      if (fieldFilter) params.field = fieldFilter;
      if (search.trim()) params.search = search.trim();

      const issuesRes = await api.get<DataQualityIssuesResponse>("/data-quality/issues", { params });
      setIssuesData(issuesRes.data);
    } catch (err: any) {
      console.error("Error loading quality data:", err);
      setError("Failed to fetch quality report from backend.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [dataset, severityFilter, fieldFilter, search, page]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const severityCounts = report?.severity_counts || { ERROR: 0, WARNING: 0, INFO: 0 };
  const totalIssues = report?.total_issues_count || 0;
  const isHealthy = severityCounts.ERROR === 0;

  return (
    <div className="min-h-screen bg-background text-foreground pb-24">
      {/* Header */}
      <div className="border-b border-white/10 bg-gradient-to-b from-primary/10 via-background to-background py-10 px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-primary/30 bg-primary/10 text-primary text-xs font-semibold uppercase tracking-wider mb-3">
                <ShieldCheck className="h-3.5 w-3.5" />
                Automated Quality Checker
              </div>
              <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight">
                Data Quality & <span className="text-primary">Integrity Dashboard</span>
              </h1>
              <p className="mt-2 text-sm sm:text-base text-muted-foreground max-w-2xl">
                Non-destructive audit of vehicle catalog entries, launch classifications, numeric bounds, EV powertrain consistency, and duplicate detection.
              </p>
            </div>

            {/* Dataset Selector & Refresh */}
            <div className="flex items-center gap-3">
              <div className="flex p-1 rounded-xl border border-white/10 bg-card/60 backdrop-blur-md">
                <button
                  onClick={() => {
                    setDataset("new_launches");
                    setPage(1);
                  }}
                  className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition ${
                    dataset === "new_launches"
                      ? "bg-primary text-primary-foreground shadow"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  New Launches (CarWale)
                </button>
                <button
                  onClick={() => {
                    setDataset("catalog");
                    setPage(1);
                  }}
                  className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition ${
                    dataset === "catalog"
                      ? "bg-primary text-primary-foreground shadow"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  Catalog (cars_main.csv)
                </button>
              </div>

              <button
                onClick={() => fetchData(true)}
                disabled={refreshing}
                title="Re-run audit checks"
                className="p-2.5 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 text-muted-foreground hover:text-foreground transition disabled:opacity-50"
              >
                <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin text-primary" : ""}`} />
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 mt-8">
        {/* KPI Summary Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
          {/* Health Status */}
          <div className="rounded-2xl border border-white/10 bg-card/40 backdrop-blur-md p-4">
            <span className="text-xs text-muted-foreground flex items-center justify-between">
              Health Status
              {isHealthy ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              ) : (
                <AlertOctagon className="h-4 w-4 text-destructive" />
              )}
            </span>
            <div className={`text-xl font-extrabold mt-1 ${isHealthy ? "text-emerald-400" : "text-destructive"}`}>
              {isHealthy ? "HEALTHY" : "ATTENTION"}
            </div>
            <span className="text-[11px] text-muted-foreground">
              {severityCounts.ERROR === 0 ? "0 blocking errors" : `${severityCounts.ERROR} errors found`}
            </span>
          </div>

          {/* Total Examined */}
          <div className="rounded-2xl border border-white/10 bg-card/40 backdrop-blur-md p-4">
            <span className="text-xs text-muted-foreground flex items-center justify-between">
              Examined Rows
              <Database className="h-4 w-4 text-blue-400" />
            </span>
            <div className="text-xl font-extrabold text-foreground mt-1">
              {report?.total_rows ?? "..."}
            </div>
            <span className="text-[11px] text-muted-foreground">Across {report?.total_columns ?? 0} fields</span>
          </div>

          {/* Critical Errors */}
          <div className="rounded-2xl border border-white/10 bg-card/40 backdrop-blur-md p-4">
            <span className="text-xs text-muted-foreground flex items-center justify-between">
              Integrity Errors
              <AlertOctagon className="h-4 w-4 text-destructive" />
            </span>
            <div className="text-xl font-extrabold text-destructive mt-1">
              {severityCounts.ERROR}
            </div>
            <span className="text-[11px] text-muted-foreground">Requires fix</span>
          </div>

          {/* Warnings */}
          <div className="rounded-2xl border border-white/10 bg-card/40 backdrop-blur-md p-4">
            <span className="text-xs text-muted-foreground flex items-center justify-between">
              Warnings
              <AlertTriangle className="h-4 w-4 text-amber-400" />
            </span>
            <div className="text-xl font-extrabold text-amber-400 mt-1">
              {severityCounts.WARNING}
            </div>
            <span className="text-[11px] text-muted-foreground">Plausibility / Specs</span>
          </div>

          {/* Duplicates */}
          <div className="rounded-2xl border border-white/10 bg-card/40 backdrop-blur-md p-4">
            <span className="text-xs text-muted-foreground flex items-center justify-between">
              Duplicates
              <Layers className="h-4 w-4 text-purple-400" />
            </span>
            <div className="text-xl font-extrabold text-purple-400 mt-1">
              {report?.duplicate_analysis?.exact_duplicate_rows_count ?? 0}
            </div>
            <span className="text-[11px] text-muted-foreground">Exact row copies</span>
          </div>

          {/* Records Requiring Review */}
          <div className="rounded-2xl border border-white/10 bg-card/40 backdrop-blur-md p-4">
            <span className="text-xs text-muted-foreground flex items-center justify-between">
              Under Review
              <Clock className="h-4 w-4 text-primary" />
            </span>
            <div className="text-xl font-extrabold text-primary mt-1">
              {report?.records_requiring_manual_review ?? 0}
            </div>
            <span className="text-[11px] text-muted-foreground">Flagged records</span>
          </div>
        </div>

        {/* Missing Data Analysis Section */}
        {report?.missing_data_analysis?.fields && (
          <div className="rounded-2xl border border-white/10 bg-card/40 backdrop-blur-xl p-6 mb-8 shadow-lg">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
              <div>
                <h3 className="text-lg font-bold text-foreground flex items-center gap-2">
                  <BarChart3 className="h-5 w-5 text-primary" />
                  Powertrain-Aware Missing Data Analysis
                </h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Adjusted for legitimate powertrain differences (e.g. Electric vehicles legitimately lack engine displacement; ICE vehicles lack traction batteries).
                </p>
              </div>

              {report.missing_data_analysis.ev_records_count !== undefined && (
                <div className="flex gap-2 text-xs">
                  <span className="px-2.5 py-1 rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400 font-medium">
                    ⚡ {report.missing_data_analysis.ev_records_count} EVs
                  </span>
                  <span className="px-2.5 py-1 rounded-lg border border-blue-500/30 bg-blue-500/10 text-blue-400 font-medium">
                    ⛽ {report.missing_data_analysis.ice_records_count} ICE
                  </span>
                </div>
              )}
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3 pt-2">
              {Object.entries(report.missing_data_analysis.fields).map(([fieldName, stats]) => {
                const adjPct = stats.adjusted_missing_percentage;
                return (
                  <div key={fieldName} className="bg-white/5 border border-white/5 rounded-xl p-3">
                    <span className="text-xs font-mono text-muted-foreground block truncate">{fieldName}</span>
                    <div className="flex items-baseline justify-between mt-1">
                      <span className="text-lg font-bold">{adjPct}%</span>
                      <span className="text-[11px] text-muted-foreground">{stats.adjusted_missing_count} missing</span>
                    </div>
                    {/* Progress Bar */}
                    <div className="w-full h-1 bg-white/10 rounded-full mt-2 overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          adjPct === 0 ? "bg-emerald-400" : adjPct < 15 ? "bg-amber-400" : "bg-destructive"
                        }`}
                        style={{ width: `${Math.min(100, adjPct)}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Filterable Issues Table */}
        <div className="rounded-2xl border border-white/10 bg-card/40 backdrop-blur-xl p-6 shadow-xl">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
            <div>
              <h3 className="text-lg font-bold text-foreground flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-amber-400" />
                Data Quality Issues Log ({issuesData?.total ?? 0})
              </h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                Detailed audit trail with recommended non-destructive resolution actions.
              </p>
            </div>

            {/* Filters */}
            <div className="flex flex-wrap items-center gap-2">
              {/* Search */}
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                <input
                  type="text"
                  value={search}
                  onChange={(e) => {
                    setSearch(e.target.value);
                    setPage(1);
                  }}
                  placeholder="Search issues..."
                  className="pl-8 pr-3 py-1.5 rounded-xl border border-white/10 bg-background/80 text-xs focus:outline-none focus:border-primary transition w-44"
                />
              </div>

              {/* Severity Filter */}
              <select
                value={severityFilter}
                onChange={(e) => {
                  setSeverityFilter(e.target.value);
                  setPage(1);
                }}
                className="px-3 py-1.5 rounded-xl border border-white/10 bg-background/80 text-xs focus:outline-none focus:border-primary transition"
              >
                <option value="">All Severities</option>
                <option value="ERROR">Errors Only</option>
                <option value="WARNING">Warnings Only</option>
                <option value="INFO">Info Only</option>
              </select>
            </div>
          </div>

          {/* Table */}
          {issuesData?.items && issuesData.items.length > 0 ? (
            <div className="overflow-x-auto rounded-xl border border-white/10">
              <table className="w-full text-left text-xs">
                <thead className="bg-white/5 border-b border-white/10 text-muted-foreground uppercase text-[10px] tracking-wider font-semibold">
                  <tr>
                    <th className="py-3 px-4">Severity</th>
                    <th className="py-3 px-4">Record ID</th>
                    <th className="py-3 px-4">Vehicle</th>
                    <th className="py-3 px-4">Field</th>
                    <th className="py-3 px-4">Issue Type</th>
                    <th className="py-3 px-4">Observed Value</th>
                    <th className="py-3 px-4">Recommended Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5 font-sans">
                  {issuesData.items.map((issue, idx) => {
                    const isErr = issue.severity === "ERROR";
                    const isWarn = issue.severity === "WARNING";
                    return (
                      <tr key={idx} className="hover:bg-white/[0.02] transition">
                        <td className="py-3 px-4">
                          <span
                            className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                              isErr
                                ? "bg-destructive/15 text-destructive border-destructive/30"
                                : isWarn
                                ? "bg-amber-500/15 text-amber-400 border-amber-500/30"
                                : "bg-blue-500/15 text-blue-400 border-blue-500/30"
                            }`}
                          >
                            {issue.severity}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-mono text-muted-foreground">{issue.record_id}</td>
                        <td className="py-3 px-4">
                          <div className="font-semibold text-foreground">
                            {issue.brand} {issue.model}
                          </div>
                          {issue.variant && (
                            <div className="text-[11px] text-muted-foreground font-mono">{issue.variant}</div>
                          )}
                        </td>
                        <td className="py-3 px-4 font-mono text-primary">{issue.field}</td>
                        <td className="py-3 px-4 font-medium">{issue.issue_type}</td>
                        <td className="py-3 px-4 font-mono text-muted-foreground max-w-[150px] truncate">
                          {issue.observed_value || "—"}
                        </td>
                        <td className="py-3 px-4 text-muted-foreground max-w-[260px]">{issue.recommended_action}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="py-12 text-center rounded-xl border border-white/5 bg-white/[0.01]">
              <CheckCircle2 className="h-10 w-10 text-emerald-400 mx-auto mb-2" />
              <h4 className="text-base font-bold text-foreground">Zero Quality Issues Flagged</h4>
              <p className="text-xs text-muted-foreground mt-1 max-w-sm mx-auto">
                All records in this dataset adhere to strict numeric plausibility, required fields, and powertrain consistency rules.
              </p>
            </div>
          )}

          {/* Pagination */}
          {issuesData && issuesData.total > 50 && (
            <div className="flex items-center justify-between pt-4 mt-2 text-xs text-muted-foreground">
              <span>
                Showing {(page - 1) * 50 + 1} to {Math.min(page * 50, issuesData.total)} of {issuesData.total} issues
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-3 py-1.5 rounded-lg border border-white/10 bg-white/5 hover:bg-white/10 disabled:opacity-40 transition"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage((p) => p + 1)}
                  disabled={page * 50 >= issuesData.total}
                  className="px-3 py-1.5 rounded-lg border border-white/10 bg-white/5 hover:bg-white/10 disabled:opacity-40 transition"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
