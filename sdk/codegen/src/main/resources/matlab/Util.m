classdef (Abstract) Util
    methods(Static)
        function result = secondsToYears(seconds)
            result = seconds / 31557600.0;
        end
        function result = yearsToSeconds(years)
            result = int64(years * 31557600.0);
        end
        function result = secondsToMonths(seconds)
            result = seconds / 2592000.0;
        end
        function result = monthsToSeconds(months)
            result = int64(months * 2592000.0);
        end
        function result = secondsToWeeks(seconds)
            result = seconds / 604800.0;
        end
        function result = weeksToSeconds(weeks)
            result = int64(weeks * 604800.0);
        end
        function result = secondsToDays(seconds)
            result = seconds / 86400.0;
        end
        function result = daysToSeconds(days)
            result = int64(days * 86400.0);
        end
    end
end