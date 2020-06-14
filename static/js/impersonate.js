// Allows certain users to view the website as if they were other users. Also
// includes routines that let researchers create new users for testing
// purposes, which requires setting up fake entities (cohorts, schools,
// classrooms, etc.)

function ImpersonateController($scope, $pertsAjax, $q, $timeout, $window) {
    'use strict';
    
    $scope.userIndex = {};
    $scope.alert = false;
    $scope.currentlyImpersonating = $window.currentlyImpersonating;

    // program id to dictionary of populated entities
    $scope.contexts = {};

    $scope.demoUrlPattern =
        /https?:\/\/\S+?\/p\/(\S+?)\/(student|teacher)\?\S+?#(.*)/;

    if (queryString('permission_denied') === 'true') {
        $scope.alert = {
            type: 'error',
            msg: "You don't have permission to impersonate that user"
        };
    } else {
        $scope.alert = false;
    }

    // Populate the program choices
    $pertsAjax({url: '/api/get/program'}).then(function (response) {
        $scope.programList = response;
    });

    $scope.getUserByEmail = function (email) {
        $scope.impersonationError = '';
        return $pertsAjax({
            url: '/api/get/user',
            params: {login_email: email}
        }).then(function (userList) {
            if (userList.length === 1) {
                return userList[0];
            } else {
                $scope.impersonationError = "User not found.";
            }
        });
    };

    // Given a user's id or email, immediately impersonate that person.
    $scope.impersonate = function () {
        var promise;
        if ($scope.email_or_id.contains('@')) {
            // Then we have an email. Look up the user.
            promise = $scope.getUserByEmail($scope.email_or_id);
        } else if ($scope.email_or_id.contains('User_')) {
            // Then we have a user id. Wrap it in a promise that imitates the
            // email-based fetch.
            var deferred = $q.defer();
            deferred.resolve();
            promise = deferred.promise.then(function () {
                // a pretend user object
                return {id: $scope.email_or_id};
            });
        }
        promise.then(function (target) {
            if (!target) { return; }
            $window.location.href = '?page_action=impersonate&target=' +
                target.id;
        });
    };

    // Given a set of testing data, enter the program app as a either a teacher
    // or a student (whom have just been created).
    $scope.testAs = function (userType) {
        var context = $scope.contexts[$scope.selectedProgram.id];
        var link = $scope.buildProgramLink(userType);
        $window.location.href = '?page_action=impersonate&target=' +
            context[userType].id + '&redirect=' + encodeURIComponent(link);
    };

    // Use testing data to build the correct url for the program app.
    $scope.buildProgramLink = function (userType, position) {
        // portion of the url that is the same for all users
        var context = $scope.contexts[$scope.selectedProgram.id];
        var url = '//' + $window.location.host + '/p/' +
            $scope.selectedProgram.abbreviation + '/' + userType + '?' +
            'cohort=' + context.cohort.id;
        // only students get the classroom parameter
        if (userType === 'student') {
            url += '&classroom=' + context.classroom.id;
        }
        // Point to a specific page in the program, if specified. This is
        // generally used for demo emails, and generally not used for the
        // one-click-test-as buttons.
        if (position) {
            url += '#' + position;
        }
        return url;
    };

    // A mini populate script that just creates what is necesary to test the
    // program app.
    $scope.createTestContext = function (program) {
        var demoId = Math.floor(Math.random() * (100000000)) + 10000000;
        var commands = [
            {
                'name': 'school',
                'description': 'Create test school',
                'command':
                    '/api/put/school?name=TestSchool&is_test=true'
            },
            {
                'name': 'cohort',
                'description': 'Create test cohort',
                'command':
                    '/api/put/cohort?code=[%demoId%]&name=TestCohort&program=[%program.id%]&school=[%responses.school.id%]&is_test=true'
            },
            {
                'name': 'teacher',
                'description': 'Create test teacher',
                'command':
                    '/api/put/user?plaintext_password=startdemo&user_type=teacher&login_email=[%demoId%]@a.aa&name=[%demoId%]@a.aa&auth_id=direct_[%demoId%]@a.aa&registration_complete=true&is_test=true'
            },
            // have the teacher associate themselves to the cohort
            // (activities come back in the server resonse when teachers are associated
            // to a cohort).
            {
                'name': 'teacher_to_cohort',
                'description': 'Associate teacher to cohort',
                'command':
                    '/api/associate/user/[%responses.teacher.id%]/cohort/[%responses.cohort.id%]?impersonate=[%responses.teacher.id%]&is_test=true'
            },
            // have the teacher create a classroom
            // (student activities come back in the server resonse as a property of the
            // classroom)
            {
                'name': 'classroom',
                'description': 'Create test classroom',
                'command':
                    '/api/put/classroom?user=[%responses.teacher.id%]&cohort=[%responses.cohort.id%]&program=[%program.id%]&name=TestClassroom&impersonate=[%responses.teacher.id%]&is_test=true'
            },
            {
                'name': 'student',
                'description': 'Create test student',
                'command':
                '/api/put/user?classroom=[%responses.classroom.id%]&birth_date=[%(new Date()).toDateString("local")%]&first_name=test&last_name=student&user_type=student&is_test=true'
            }
        ];

        var errorsOccurred = false;

        // parse commands
        var parseCommand = function (text, responses) {
            
            // extraction pattern
            //
            // This regex will grab both the string to be replaced which
            // includes brackets and the string to be executed which is
            // within the string to be replaced and has no brackets.
            // 
            // e.g. 
            //      'command/[%5+5%]/more'  ->  ['[%5+5%]', '5+5']
            //
            var pattern = /\[%([^%]*)%\]/;

            // find all
            var match;
            while (match = pattern.exec(text)) {
                // evaluate and replace
                text = text.replace(match[0], eval(match[1]));
            }
            return text;
        };


        // api calls
        var run = function (commands, responses) {

            // unpack
            var next = commands.shift();
            var name = next.name;
            var description = parseCommand(next.description, responses);
            var command = parseCommand(next.command, responses);
            // Delay lets us avoid GAE's sometimes inconsistent results;
            // only used when creating something and then immediately
            // getting it through a separate call.
            var delay = next.delay || 0;

            // api call
            $.get(command, function (response) {
                // notify
                var label;
                if (response.success) {
                    label = 'success';
                } else {
                    label = '<span style="color:red">failed</span>';
                    errorsOccurred = true;
                }

                $('#commands').append(description + '...' + label + '\n');

                // record responses
                responses[name] = response.data;

                // recurse
                if (commands.length > 0) {
                    $timeout(function () {
                        run(commands, responses);
                    }, delay * 1000);
                } else {
                    if (errorsOccurred) {
                        $('#commands').append('COMPLETE WITH ERRORS\n');
                    } else {
                        $('#commands').append('COMPLETE\n');
                        $scope.$apply(function(){responses.complete = true;});
                    }
                }
            });
        };

        // initiate
        $scope.contexts[program.id] = {demoUrls: []};
        run(commands, $scope.contexts[program.id]);
    };

    // Create a demo url based on the subprogram (student or teacher) and
    // position defined by the user. The user specifies this by providing a
    // sample url. The cohort (and maybe classroom) of this sample url is
    // irrelevant; we'll use the testing data (context) for that.
    $scope.newDemoURL = function () {
        var parts = $scope.demoUrlPattern.exec($scope.newDemoUrl);
        var programAbbreviation = parts[1];
        var subprogram = parts[2];
        var position = parts[3];

        if (programAbbreviation !== $scope.selectedProgram.abbreviation) {
            alert("The URL doesn't match the program you selected.");
            return;
        }

        var loginUrl = '//' + $window.location.host + '/login?redirect=';
        var redirectUrl = $scope.buildProgramLink(subprogram, position);
        var completeUrl = loginUrl + encodeURIComponent(redirectUrl);
        var label = $scope.newDemoLabel;
        $scope.contexts[$scope.selectedProgram.id].demoUrls.push(
            {'url': completeUrl, 'label': label});
    };
}
