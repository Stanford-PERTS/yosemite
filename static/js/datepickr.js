/*
    datepickr - pick your date not your nose
    Copyright (c) 2012

    Original documentation:
    https://code.google.com/p/datepickr/wiki/Documentation

    CAM modified:
        new config options:
            dateOpen: 'yyyy-mm-dd'
            dateClosed: 'yyyy-mm-dd'

        new signature:
            supply a DOM node, not an id, e.g.
            new datepickr(document.getElementById('myNode'));

        new methods:
            setDate(localDateObject)
            // used internally

            value()
            // returns _currentValue

        new property:
            _currentValue
            // the date the user has set in this calendar, as a local date obj
*/

var datepickr = (function() {
    var datepickrs = [],
    currentDate = new Date(),
    date = {
        current: {
            year: function() {
                return currentDate.getFullYear();
            },
            month: {
                integer: function() {
                    return currentDate.getMonth();
                },
                string: function(full) {
                    var date = currentDate.getMonth();
                    return monthToStr(date, full);
                }
            },
            day: function() {
                return currentDate.getDate();
            }
        },
        month: {
            string: function(full, currentMonthView) {
                var date = currentMonthView;
                return monthToStr(date, full);
            },
            numDays: function(currentMonthView, currentYearView) {
                // checks to see if february is a leap year otherwise return the respective # of days
                return (currentMonthView == 1 && !(currentYearView & 3) && (currentYearView % 1e2 || !(currentYearView % 4e2))) ? 29 : daysInMonth[currentMonthView];
            }
        }
    },
    weekdays = ['Sun', 'Mon', 'Tues', 'Wednes', 'Thurs', 'Fri', 'Satur'],
    months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
    daysInMonth = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31],
    suffix = { 1: 'st', 2: 'nd', 3: 'rd', 21: 'st', 22: 'nd', 23: 'rd', 31: 'st' },
    buildCache = [],
    handlers = {
        calendarClick: function(e) {
            if (e.target.className) {
                switch(e.target.className) {
                    case 'prev-month':
                    case 'prevMonth':
                        this.currentMonthView--;
                        if(this.currentMonthView < 0) {
                            this.currentYearView--;
                            this.currentMonthView = 11;
                        }
                        rebuildCalendar.call(this);
                    break;
                    case 'next-month':
                    case 'nextMonth':
                        this.currentMonthView++;
                        if(this.currentMonthView > 11) {
                            this.currentYearView++;
                            this.currentMonthView = 0;
                        }
                        rebuildCalendar.call(this);
                    break;
                    case 'day':
                        var isDisabled = $(e.target).parent().hasClass('disabled');
                        if (!isDisabled) {
                            var day = e.target.innerHTML;
                            var date = new Date(this.currentYearView, this.currentMonthView, day);
                            this.setDate(date);
                            this.close();
                        }
                    break;
                }
            }
        },
        documentClick: function(e) {
            if (e.target != this.element && e.target != this.calendar) {
                var parentNode = e.target.parentNode;
                if(parentNode != this.calender) {
                    while(parentNode != this.calendar) {
                        parentNode = parentNode.parentNode;
                        if(parentNode == null) {
                            this.close();
                            break;
                        }
                    }
                }
            }
        }
    };

    // Incomplete implementation of php's date() syntax. See:
    // http://us1.php.net/manual/en/function.date.php
    function formatDate(dateObj, dateFormat) {
        if (dateFormat === 'byLocale') {
            return dateObj.toLocaleDateString();
        }

        var formattedDate = '',
        format = {
            //// Day
            // Day of the month, 2 digits with leading zeros
            // 01 to 31
            d: function () {
                var day = format.j();
                return (day < 10) ? '0' + day : day;
            },
            // A textual representation of a day, three letters
            // Mon through Sun
            D: function () {
                return weekdays[format.w()].substring(0, 3);
            },
            // Day of the month without leading zeros
            // 1 to 31
            j: function () {
                return dateObj.getDate();
            },
            // A full textual representation of the day of the week
            // Sunday through Saturday
            l: function () {
                return weekdays[format.w()] + 'day';
            },
            // English ordinal suffix for the day of the month, 2 characters
            // st, nd, rd or th. Works well with j
            S: function () {
                return suffix[format.j()] || 'th';
            },
            // Numeric representation of the day of the week
            // 0 (for Sunday) through 6 (for Saturday)
            w: function () {
                return dateObj.getDay();
            },
            //// Month
            // A full textual representation of a month
            // January through December
            F: function () {
                return monthToStr(dateObj.getMonth(), true);
            },
            // Numeric representation of a month, with leading zerosi
            // 01 through 12
            m: function () {
                var month = dateObj.getMonth() + 1;
                return (month < 10) ? '0' + month : month;
            },
            // A short textual representation of a month, three letters
            // Jan through Dec
            M: function () {
                return monthToStr(dateObj.getMonth(), false);
            },
            // Numeric representation of a month, without leading zeros
            // 1 through 12
            n: function () {
                return dateObj.getMonth() + 1;
            },
            //// Year
            // A full numeric representation of a year, 4 digits
            // 1999 or 2003
            Y: function () {
                return dateObj.getFullYear();
            },
            // A two digit representation of a year
            // 99 or 03
            y: function () {
                return format.Y().toString().substring(2, 4);
            }
        },
        formatPieces = dateFormat.split('');

        foreach(formatPieces, function(formatPiece) {
            formattedDate += format[formatPiece] ? format[formatPiece]() : formatPiece;
        });

        return formattedDate;
    }

    function foreach(items, callback) {
        var i = 0, x = items.length;
        for(i; i < x; i++) {
            if(callback(items[i], i) === false) {
                break;
            }
        }
    }

    function addEvent(element, eventType, callback) {
        if(element.addEventListener) {
            element.addEventListener(eventType, callback, false);
        } else if(element.attachEvent) {
            var fixedCallback = function(e) {
                e = e || window.event;
                e.preventDefault = (function(e) {
                    return function() { e.returnValue = false; }
                })(e);
                e.stopPropagation = (function(e) {
                    return function() { e.cancelBubble = true; }
                })(e);
                e.target = e.srcElement;
                callback.call(element, e);
            };
            element.attachEvent('on' + eventType, fixedCallback);
        }
    }

    function removeEvent(element, eventType, callback) {
        if(element.removeEventListener) {
            element.removeEventListener(eventType, callback, false);
        } else if(element.detachEvent) {
            element.detachEvent('on' + eventType, callback);
        }
    }

    function buildNode(nodeName, attributes, content) {
        var element;

        if(!(nodeName in buildCache)) {
            buildCache[nodeName] = document.createElement(nodeName);
        }

        element = buildCache[nodeName].cloneNode(false);

        if(attributes != null) {
            for(var attribute in attributes) {
                element[attribute] = attributes[attribute];
            }
        }

        if(content != null) {
            if(typeof(content) == 'object') {
                element.appendChild(content);
            } else {
                element.innerHTML = content;
            }
        }

        return element;
    }

    function monthToStr(date, full) {
        return ((full == true) ? months[date] : ((months[date].length > 3) ? months[date].substring(0, 3) : months[date]));
    }

    function isToday(day, currentMonthView, currentYearView) {
        return day == date.current.day() && currentMonthView == date.current.month.integer() && currentYearView == date.current.year();
    }

    function isSelected(selectedDate, day, currentMonthView, currentYearView) {
        if (!selectedDate) { return false; }
        return selectedDate.getDate() === day &&
               selectedDate.getMonth() === currentMonthView &&
               selectedDate.getFullYear() === currentYearView;
    }

    function buildWeekdays() {
        var weekdayHtml = document.createDocumentFragment();
        foreach(weekdays, function(weekday) {
            weekdayHtml.appendChild(buildNode('th', {}, weekday.substring(0, 2)));
        });
        return weekdayHtml;
    }

    function rebuildCalendar() {
        while(this.calendarBody.hasChildNodes()){
            this.calendarBody.removeChild(this.calendarBody.lastChild);
        }

        var firstOfMonth = new Date(this.currentYearView, this.currentMonthView, 1).getDay(),
        numDays = date.month.numDays(this.currentMonthView, this.currentYearView);

        this.currentMonth.innerHTML = date.month.string(this.config.fullCurrentMonth, this.currentMonthView) + ' ' + this.currentYearView;
        this.calendarBody.appendChild(buildDays.call(this, firstOfMonth, numDays, this.currentMonthView, this.currentYearView));
    }

    function buildCurrentMonth(config, currentMonthView, currentYearView) {
        return buildNode('span', { className: 'current-month' }, date.month.string(config.fullCurrentMonth, currentMonthView) + ' ' + currentYearView);
    }

    function buildMonths(config, currentMonthView, currentYearView) {
        var months = buildNode('div', { className: 'months' }),
        prevMonth = buildNode('span', { className: 'prev-month' }, buildNode('span', { className: 'prevMonth' }, '&lt;')),
        nextMonth = buildNode('span', { className: 'next-month' }, buildNode('span', { className: 'nextMonth' }, '&gt;'));

        months.appendChild(prevMonth);
        months.appendChild(nextMonth);

        return months;
    }

    function buildDays(firstOfMonth, numDays, currentMonthView, currentYearView) {
        var calendarBody = document.createDocumentFragment(),
        row = buildNode('tr'),
        dayCount = 0, i;
        // print out previous month's "days"
        for(i = 1; i <= firstOfMonth; i++) {
            row.appendChild(buildNode('td', null, '&nbsp;'));
            dayCount++;
        }

        var dateOpen, dateClosed;
        if (this.config.dateOpen) {
            dateOpen = Date.createFromString(this.config.dateOpen, 'local');
        }
        if (this.config.dateClosed) {
            dateClosed = Date.createFromString(this.config.dateClosed, 'local');
        }

        for(i = 1; i <= numDays; i++) {
            // if we have reached the end of a week, wrap to the next line
            if(dayCount == 7) {
                calendarBody.appendChild(row);
                row = buildNode('tr');
                dayCount = 0;
            }

            var dateString = i < 10 ? '0' + i : '' + i;
            var month = currentMonthView + 1;
            var monthString = month < 10 ? '0' + month : '' + month;
            var todayString = currentYearView + '-' + monthString + '-' + dateString;
            var today = Date.createFromString(todayString, 'local');

            var attributes = {};
            classNames = [];
            if (isToday(i, currentMonthView, currentYearView)) {
                classNames.push('today');
            }
            if (isSelected(this._currentValue, i, currentMonthView, currentYearView)) {
                classNames.push('selected');
            }
            if (this.config.dateOpen) {
                if (dateOpen > today) {
                    classNames.push('disabled');
                }
            }
            if (this.config.dateClosed) {
                // dateClosed means that, on that date, the program is closed.
                // So the last day available for scheduling is the day before.
                if (dateClosed <= today) {
                    classNames.push('disabled');
                }
            }
            if (classNames.length > 0) {
                attributes.className = classNames.join(' ');
            }
            row.appendChild(buildNode('td', attributes, buildNode('span', { className: 'day' }, i)));

            dayCount++;
        }

        // if we haven't finished at the end of the week, start writing out the "days" for the next month
        for(i = 1; i <= (7 - dayCount); i++) {
            row.appendChild(buildNode('td', null, '&nbsp;'));
        }

        calendarBody.appendChild(row);

        return calendarBody;
    }

    function buildCalendar() {
        var firstOfMonth = new Date(this.currentYearView, this.currentMonthView, 1).getDay(),
        numDays = date.month.numDays(this.currentMonthView, this.currentYearView),
        self = this;

        this.calendarContainer = buildNode('div', { className: 'calendar' });
        positionCalendar.call(this);

        this.currentMonth = buildCurrentMonth(this.config, this.currentMonthView, this.currentYearView)
        var months = buildMonths(this.config, this.currentMonthView, this.currentYearView);
        months.appendChild(this.currentMonth);

        var calendar = buildNode('table', null, buildNode('thead', null, buildNode('tr', { className: 'weekdays' }, buildWeekdays())));
        this.calendarBody = buildNode('tbody');
        this.calendarBody.appendChild(buildDays.call(this, firstOfMonth, numDays, this.currentMonthView, this.currentYearView));
        calendar.appendChild(this.calendarBody);

        this.calendarContainer.appendChild(months);
        this.calendarContainer.appendChild(calendar);

        document.body.appendChild(this.calendarContainer);

        addEvent(this.calendarContainer, 'click', function(e) { handlers.calendarClick.call(self, e); });

        return this.calendarContainer;
    }

    function positionCalendar() {
        var inputLeft = inputTop = 0,
        obj = this.element;

        if(obj.offsetParent) {
            do {
                inputLeft += obj.offsetLeft;
                inputTop += obj.offsetTop;
            } while (obj = obj.offsetParent);
        }
        this.calendarContainer.style.cssText = 'display: none; position: absolute; top: ' + (inputTop + this.element.offsetHeight) + 'px; left: ' + inputLeft + 'px; z-index: 100;';
    }

    // return function(elementId, userConfig) {
    var datepickr = function(node, userConfig) {
        var self = this;

        // this.element = document.getElementById(elementId);
        this.element = node;
        $(this.element).attr('readonly', 'readonly');
        this.element.value = 'set date';

        this.config = {
            fullCurrentMonth: true,
            dateFormat: 'F jS, Y'
        };
        this.currentYearView = date.current.year();
        this.currentMonthView = date.current.month.integer();

        this.valid = true;

        if(userConfig) {
            for(var key in userConfig) {
                this.config[key] = userConfig[key];
            }
        }

        this.documentClick = function(e) { handlers.documentClick.call(self, e); }

        this.setDate = function (date) {
            this.element.value = formatDate(date, this.config.dateFormat);
            this._currentValue = date;
            this.element._currentValue = date;
            $(this.element).addClass('is-set');
        };

        this.getValue = function () {
            if (this._currentValue) {
                return this._currentValue;
            } else {
                return undefined;
            }
        };

        this.open = function(e) {
            addEvent(document, 'click', self.documentClick);

            foreach(datepickrs, function(datepickr) {
                if(datepickr != self) {
                    datepickr.close();
                }
            });

            positionCalendar.call(self);
            self.calendar.style.display = 'block';
        };

        this.close = function(e) {
            removeEvent(document, 'click', self.documentClick);
            self.calendar.style.display = 'none';
        };

        this.markValid = function () {
            $(this.element).addClass('valid');
            $(this.element).removeClass('invalid');
            $('i', this.element.parentNode).remove();
            this.valid = true;
        };

        this.markInvalid = function () {
            $(this.element).addClass('invalid');
            $(this.element).removeClass('valid');
            this.valid = false;
        };

        this.rebuild = function () {
            var isValid,
                dateOpen,
                dateClosed;
            if (this.config.dateOpen) {
                dateOpen = Date.createFromString(this.config.dateOpen, 'local');
            }
            if (this.config.dateClosed) {
                dateClosed = Date.createFromString(this.config.dateClosed, 'local');
            }

            if (this._currentValue) {
                if (
                    (dateOpen && this._currentValue < dateOpen) ||
                    (dateClosed && this._currentValue > dateClosed)
                ) {
                    isValid = false;
                    this.markInvalid();
                } else {
                    isValid = true;
                    this.markValid();
                }
            }
            rebuildCalendar.call(self);
            return isValid;
        };
        this.calendar = buildCalendar.call(this);

        datepickrs.push(this);

        if(this.element.nodeName == 'INPUT') {
            addEvent(this.element, 'focus', this.open);
        } else {
            addEvent(this.element, 'click', this.open);
        }
    };

    datepickr.formatDate = formatDate;

    return datepickr;
})();