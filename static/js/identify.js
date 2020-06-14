// Javascript for student sign in.

function IdentifyController($scope, $pertsAjax, $timeout, $window) {
    'use strict';

    var x;
    // This phase var will be used for ng-show in place of the partialMatches
    // 'phase 0' is the participation code box
    // 'phase 1' contains classroom dropdown, nickname, first, and last
    // 'phase 2' corresponds to the partial matches div.
    // 'phase 3' corresponds to the new user div.
    $scope.phase = 0;
    $scope.doubleCheckNewUser = false;

    // Cohort/session code must be two words and then a digit, separated by
    // single spaces.
    $scope.codeRegex = /^(\S+ \S+) ([1])$/;

    $scope.days = [];
    for (x = 1; x <= 31; x += 1) { $scope.days.push(x); }

    $scope.months = ['January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'];

    $scope.years = [];
    for (x = 2010; x >= 1940; x -= 1) { $scope.years.push(x); }

    // These two are used in ng-show directives
    $scope.classroomList = [];
    $scope.partialMatches = [];  // will be an array

    $scope.identifyData = {};

    $scope.nonStudentLogIn = window.nonStudentLogIn;
    $scope.studentAlreadyLoggedIn = window.studentAlreadyLoggedIn;

    $scope.$watch('birth', function (value) {
        var b = $scope.birth;
        if (b && b.year && b.month && b.day) {
            // Months are indexed from zero above, so this is correct.
            var d = new Date(b.year, b.month, b.day);
            $scope.identifyData.birth_date = d.toDateString('local');
        }
    }, true);

    // 10 seconds after the user starts typing the code, if they haven't typed
    // something valid yet, show them a help message.
    $scope.$watch('identifyForm.code.$pristine', function (pristine) {
        if (pristine) { return; }

        $timeout(function () {
            if ($scope.identifyForm.code.$invalid) {
                $scope.alert = {
                    type: 'info',
                    msg: "Your participation code can be obtained from " +
                         "your teacher or introductory material.<br>The " +
                         "code contains two words followed by a number, " +
                         "like &ldquo;apple parade 2&rdquo;."
                };
            }
        }, 10 * 1000);
    });

    $scope.getCohort = function (code) {
        $scope.alert = false;
        $scope.cohortLoading = true;

        // Break up the code (e.g. 'trout viper 2') into the cohort part
        // ('trout viper') and the session number ('2').
        var parts = $scope.codeRegex.exec(code.toLowerCase());
        if (parts === null) {
            // This shouldn't happen b/c angular is validating against the
            // regex before the user is allowed to get this far.
            throw new Error("Invalid code in identify: " + code);
        }
        var cohortCode = parts[1];
        $scope.sessionOrdinal = parts[2];

        var url = '/api/see/cohort?code=' + encodeURIComponent(cohortCode);
        $pertsAjax({url: url}).then(function (response) {
            $scope.cohortLoading = false;
            if (response.length === 0) {
                $scope.alert = {
                    type: 'error',
                    msg: "We don't recognize that code. Please try again."
                };
            } else {
                $scope.cohort = response[0];
                $scope.getClasses($scope.cohort);
                $scope.phase = 1;
            }
        });
    };

    $scope.getClasses = function (cohort) {
        var url = '/api/see/classroom?assc_cohort_list=' + cohort.id;
        $pertsAjax({url: url}).then(function (response) {
            if (response.length === 0) {
                $window.onerror(
                    "Cohort has no classrooms: " + cohort.name + ".");
            } else {
                $scope.classroomList = response;
            }
        });
    };

    $scope.identify = function () {
        $scope.identifyButtonClicked = true;
        $scope.identifyData.cohort = $scope.cohort.id;
        $pertsAjax({
            url: '/api/identify',
            params: $scope.identifyData
        }).then(function (response) {
            if (response === 'logout_required') {
                // Somehow the user made this call without being logged out
                // first. Force them to log out.
                $window.location.href = '/logout?redirect=/go';
            } else if (response.exact_match) {
                $scope.redirectToActivities($scope.identifyData.classroom);
            } else if (response.new_user) {
                // set double check variable to true
                $scope.doubleCheckNewUser = true;
                // set phase to 3
                $scope.phase = 3;
                $('body,html').animate({scrollTop:0},0);
            } else {
                // No exact match found, so show the user the partials.
                // Show only the first 12, so as not to overwhelm the user.
                // If the right answer isn't there, too bad...
                $scope.partialMatches = response.partial_matches.slice(0, 12);
                $scope.partialMatches.push({id: 'none', last_name: '', first_name: 'None of the above'});
                // set phase to 2
                $scope.phase = 2;
                $('body,html').animate({scrollTop:0},0);
            }
        });
    };

    $scope.choosePartialMatch = function () {
        if ($scope.partialMatchChoice === 'none') {
            // set the double check var to true
            $scope.doubleCheckNewUser = true;
            // set the phase to 3
            $scope.phase = 3;
            $('body,html').animate({scrollTop:0},0);
            // This is the way it was done in Pegasus:
            // $scope.identifyData.force_create = 'true';
            // $scope.identify();
        } else {
            var classroomId = $scope.identifyData.classroom;
            $pertsAjax({
                url: '/api/identify',
                params: {
                    user: $scope.partialMatchChoice,
                    classroom: classroomId,
                    cohort: $scope.cohort.id
                }
            }).then($scope.redirectToActivities.partial(classroomId));
        }
    };

    $scope.confirmNewUser = function () {
        $scope.confirmNewUserButtonClicked = true;
        $scope.identifyData.force_create = true;
        $scope.identify();
    };

    $scope.redirectToActivities = function (classroomId) {
        var url = '?cohort=' + $scope.cohort.id + '&classroom=' +
                  classroomId + '&session_ordinal=' + $scope.sessionOrdinal +
                  '&page_action=go_to_program';
        window.location.href = url;
    };
}
