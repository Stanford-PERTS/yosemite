// A suite of javascript tests that users can run on their device, which
// automatically reports the results back to the server. If tests fails, the
// server logs an error and will email the devs.
function ClientTestController($scope, $pertsAjax, $q, $emptyPromise, $timeout, $window) {
    'use strict';
    $scope.showClientTests = $window.userType !== 'student';
    $scope.testRunning = false;
    
    // Define unit tests here. Asynchronous test must return their promises.
    // To make tests fail, either use assert(), throw an Error, or return
    // a promise that gets rejected.
    $scope.exampleTests = {
        syncTest: function () {
            assert(true === true, "This test succeeds.");
        },
        syncFailedTest: function () {
            assert(true === false, "This test fails.");
        },
        asyncTest: function () {
            var d = $q.defer();
            d.resolve("This test succeeds.");
            return d.promise;
        },
        asyncFailedTest: function () {
            var d = $q.defer();
            d.reject("This test fails.");
            return d.promise;
        }
    };

    $scope.tests = {
        browserTest: function () {
            // We only care if you are using something older than IE 8.
            var html = $('html');
            var oldBrowserMsg = "Your browser is out of date: " +
                window.navigator.userAgent;
            // These two classes on the html element are written in by ie
            // conditional comments.
            assert(!html.hasClass('ie6') && !html.hasClass('ie7'),
                   oldBrowserMsg);
        },
        qualtricsTest: function () {
            var code = randomString(20);

            // First create a test user; everything else will be done with the
            // test user's id.
            // This put is allowed for all users including public. It's quite
            // normal for public to put students; that's how students sign in.
            var returnPromise = $pertsAjax({
                url: '/api/put/user',
                params: {
                    first_name: code,
                    last_name: code,
                    user_type: 'teacher',
                    is_test: true,
                    program: $window.programId
                }
            }).then(function (testUser) {

                // Open a qualtrics survey with the code. It should send the
                // code back via a cross site gif. The gif handler will save
                // the code on the server.
                var url = 'https://sshs.qualtrics.com/SE/?SID=SV_e3WpqPHXY7dHMKV' +
                    '&variable=cross_site_test' +
                    '&value=' + code +
                    '&user=' + testUser.id +
                    '&program=' + $window.programId +
                    '&activity_ordinal=1';

                var iframe = $('<iframe></iframe>')
                    .css({width: '700px', height: '500px'})
                    .appendTo('#client_test_div')
                    .attr('src', url);

                // Poll the server for awhile to see if the code came back.
                var codeFound = false;
                var pollingInterval = setInterval(function () {
                    $pertsAjax({
                        url: '/api/check_client_test',
                        params: {
                            cross_site_test_json: JSON.stringify({
                                code: code,
                                user_id: testUser.id
                            })
                        }
                    }).then(function (response) {
                        if (response.cross_site_test) {
                            codeFound = true;
                            clearInterval(pollingInterval);
                        }
                    });
                }, 1 * 1000);

                // Wait a little while, then report the results.
                var defer = $q.defer();
                $timeout(function () {
                    clearInterval(pollingInterval);
                    if (codeFound) {
                        defer.resolve();
                    } else {
                        defer.reject("Qualtrics did not respond.");
                    }
                    iframe.remove();
                }, 10 * 1000);

                return defer.promise;
            });

            return returnPromise;
        },
        audioTest: function () {
            // Wait a little while, then ask the user if they heard the sound
            // play.
            var defer = $q.defer();
            var message = "Did you hear any sound during the test?\n\n" +
                "Click OK if you did hear sound.\n\n" +
                "Click Cancel if you did not.";
            $timeout(function () {
                if (confirm(message)) {
                    defer.resolve();
                } else {
                    defer.reject("User did not hear sound.");
                }
            }, 10 * 1000);

            return defer.promise;
        }
    };

    // Iterate through tests, run them, collate failure messages, and
    // communicate results to server with details about the browser and user.
    $scope.runClientTests = function () {
        $scope.testRun = true;  // Communicates with UI.
        $scope.testRunning = true;  // Communicates with UI.
        var resultPromises = forEach($scope.tests, function (testName, testFn) {
            // This deferred will contain the results of the test, resolving
            // with an array of the form [success (bool), message (str)].
            var resultDeferred = $q.defer();
            // This is potentially a promise returned by the execution of the
            // test. If the returned promise (e.g. from an ajax call made
            // during the test) is rejected, we will resolve the test's
            // deferred as a failure. Tests don't have to return promises.
            var testPromise;
            // Execute the test. If it throws an error immediately, we catch
            // the it and resolve the test's deferred as a failure.
            try {
                testPromise = testFn();
            } catch (error) {
                resultDeferred.resolve(
                    [false, testName + " failed: " + error.message]);
            }
            // If this was a synchronous test and had no need to return a
            // promise, we fill in an immediately-resolving one.
            if (testPromise === undefined) {
                testPromise = $emptyPromise([true, ""]);
            }
            // If this was an asynchronous test and we don't know if it has
            // succeeded or failed yet, hook up the success or failure of the
            // test's deferred to the outcome of the test's promise.
            testPromise.then(function successCallback(response) {
                resultDeferred.resolve([true, ""]);
            }, function errorCallback(error) {
                resultDeferred.resolve(
                    [false, testName + " failed: " + error]);
            });
            // Collect all the tests' promises so we can take action when we
            // know all the results.
            return resultDeferred.promise;
        });

        // When all the asynchronous stuff is done, evaluate the results.
        $q.all(resultPromises).then(function successCallback(responses) {
            $scope.failedTests = forEach(responses, function (result) {
                if (result[0] === false) {
                    return result[1];
                }
            });

            $pertsAjax({
                url: '/api/record_client_test',
                params: {
                    failed_tests: $scope.failedTests,
                    userId: $window.userId,
                    userEmail: $window.userEmail,
                    userType: $window.userType,
                    href: $window.location.href,
                    userAgent: $window.navigator.userAgent,
                    appVersion: $window.navigator.appVersion
                },
                method: 'POST'
            }).then(function (response) {
                // Triggers a message to the user about the results.
                $scope.allTestsSuccessful = $scope.failedTests.length === 0;
                $scope.testRunning = false;
            });
        });
    };
}
