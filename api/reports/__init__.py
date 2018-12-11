from . import (
    site_report,
    project_report,
    access_log_report,
    legacy_usage_report,
    usage_report,
    daily_usage_report,
)

ReportTypes = {
    'site'            : site_report.SiteReport,
    'project'         : project_report.ProjectReport,
    'accesslog'       : access_log_report.AccessLogReport,
    'legacy-usage'    : legacy_usage_report.UsageReport,
    'usage'           : usage_report.UsageReport,
    'daily-usage'     : daily_usage_report.DailyUsageReport,
}
