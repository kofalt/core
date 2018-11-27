from . import (
    site_report, 
    project_report, 
    access_log_report,
    usage_report,
    extended_usage_report
)

ReportTypes = {
    'site'            : site_report.SiteReport,
    'project'         : project_report.ProjectReport,
    'accesslog'       : access_log_report.AccessLogReport,
    'usage'           : usage_report.UsageReport,
    'extended-usage'  : extended_usage_report.ExtendedUsageReport
}
