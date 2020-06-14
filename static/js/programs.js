// Runs the program app.
//
// Contains defintions for Postion, Module, run-through testing.

function getScope() {
    'use strict';
    return angular.element($('#appController').get()).scope();
}

function setPd(pd, v) {
    'use strict';
    var s = getScope();
    s.$apply(function () {
        s.pd[pd] = v;
    });
}

function getPd(pd) {
    'use strict';
    return getScope().pd[pd];
}

function initAutoHide() {
    'use strict';
    // apply autohiding for input types that have a concept of focus so that
    // if the user is focused on the field it stays visible
    $("input[ng-model][type='text'],textarea[ng-model]").focus(function () {
        $(this).closest('p').removeClass("autohide");
    });
    $("input[ng-model],textarea[ng-model]").blur(function () {
        $(this).closest('p').addClass("autohide");
    });

    // apply autohiding for input types that do not have a concept of focus,
    // once clicked, they will only be visible on hover
    $("input[ng-model]:not([type='text'])").click(function () {
        $(this).closest('p').addClass("autohide");
    });

    // need to use the onchange event for select nodes b/c there's an open
    // bug in chrome where onclick doesn't fire:
    // https://bugs.webkit.org/show_bug.cgi?id=60563
    $("select[ng-model]").change(function () {
        $(this).closest('p').addClass("autohide");
    });

   // add a "focused" class so that tabbed navigation always overrides auto-hide
    $("input[ng-model]:not([type='hidden']),select").each(function (i, input) {
        $(input).focus(function () {
            $(input).closest('p').addClass("focused");
        });
        $(input).blur(function () {
            $(input).closest('p').removeClass("focused");
        });
    });
}

function clientRandomizer(stratifierName) {
    'use strict';
    var proportions = window.configJson.stratifiers[stratifierName];
    // sum the weights
    var totalWeight = 0;
    /*jslint unparam: true*/
    forEach(proportions, function (group, weight) {
        totalWeight += weight;
    });
    /*jslint unparam: false*/
    // get a random value
    var randomValue = Math.floor(Math.random() * totalWeight);
    // find which bucket the value is in
    var cumulativeWeight = 0;
    var chosenGroup;
    forEach(proportions, function (group, weight) {
        cumulativeWeight += weight;
        if (chosenGroup === undefined && randomValue < cumulativeWeight) {
            chosenGroup = group;
        }
    });
    return chosenGroup;
}

function setupProgramController($scope, $pertsAjax, $forEachAsync, $q, $emptyPromise, $window) {
    'use strict';

    // Controls behavior when data can't be synched with server.
    $scope.failedPdPuts = 0;
    $scope.pdPutRetries = 3;
    // When failed puts exceed retries, this gets set to false, and the window
    // location is NOT changed.
    $scope.allowRedirect = true;

    // Tracks how frequently each pd scope is updated. We throttle puts by
    // scope because pds are stored in entity groups by scope, and GAE limits
    // how often you can write to an entity group. For example, a student
    // saving user-scope data would be writing pd with their user entity as
    // the parent.
    $scope.putTimes = {
        user: undefined,
        classroom: undefined,
        cohort: undefined
    };
    $scope.minPutInterval = 2000;  // two seconds, in milliseconds

    function InvalidPositionError(string) {
        this.name = "InvalidPositionError";
        this.message = (string || "");
    }

    InvalidPositionError.prototype = new Error();

    // To try to resolve problems with users having their sessions dropped,
    // this function is set to run every few seconds, checking if the server
    // sees them as logged in. If not, they are directed to sign in again.
    $scope.getLoggedInStatus = function () {
        $pertsAjax({url: '/api/is_logged_in'}).then(function (isLoggedIn) {
            if (!isLoggedIn) {
                $scope.handleDisconnectedUser(
                    "We've detected that you're no longer signed in.");
            }
        });
    };
    // Check every few seconds.
    // setInterval($scope.getLoggedInStatus, 5000);

    // ** Commonly used functional nodes ** //

    $scope.markProgress = function (progress) {
        console.debug("markProgress()", progress, +progress);
        var key = this.progressVariable();
        // don't overwrite any LARGER progress value
        // remember to compare integers, not strings
        if (!$scope.pd[key] || +$scope.pd[key] < +progress) {
            $scope.pd[key] = progress;
        } else {
            console.debug("skipping progress sync");
        }
    };

    // ** Position ** //

    // A valid position must match the regex and have a module part and have a
    // node part. Functional nodes may not have a page number. Segment nodes
    // may OR may not have a page number. Pageless segment positions (like
    // session_1/intro) are used in the normal flow of beginning the display of
    // segments.
/*
|         position        | matches regex? | valid? | function? | hash? |
|-------------------------|----------------|--------|-----------|-------|
| module                  | no             | --     | --        | --    |
| module/                 | no             | --     | --        | --    |
| module/intro            | yes            | yes    | no        | no    |
| module/randomize()      | yes            | yes    | yes       | no    |
| module/markProgress(25) | yes            | yes    | yes       | no    |
| module/func()/1         | yes            | no     | --        | --    |
| module/intro/1          | yes            | yes    | no        | yes   |
|-------------------------|----------------|--------|-----------|-------|
*/
    $scope.Position = function Position(positionString) {
        if (typeof positionString !== 'string') {
            throw new Error("Bad string: " + (typeof positionString) + ": " + positionString);
        }
        var matches = $scope.Position.regExp.exec(positionString);
        if (matches) {
            // lines commented with example 'session_1/markProgress(25)'
            this.module = matches[1];  // 'session_1'
            this.functionCall = matches[3];  // '(25)'
            this.isFunctional = Boolean(this.functionCall);  // sloppy conversion, turns '' and undefined into false, all other strings to true
            if (this.isFunctional) {
                this.functionName = matches[2];  // 'markProgress'
                this.node = this.functionName + this.functionCall;  // 'markProgress(25)'
                this.args = matches[4].split(',');  // ['25']
            } else {
                this.node = matches[2];
            }
            this.page = +matches[5] || undefined;  // coerce to integer
        }

        if (!matches || (this.isFunctional && this.page)) {
            throw new InvalidPositionError(positionString);
        }
    };

    /*jslint regexp: true*/
    $scope.Position.regExp = /^(.+?)\/([^\/\(]+)(\((\S*)\))?\/?(.*)/;
    /*jslint regexp: false*/

    // Explanation of the regex, in coffeescript syntax (copy and paste into
    // the "try coffeescript" section of coffeescript.org)
    // Also, see debuggex.com, it's awesome.
    /*
    ///
        ^               # begin string
        (.+?)           # module token, up to the
        /               # first slash
        (               # node name token, made of
            [^/\(]+     # any characters which are neither / nor (
        )               #
        (               # if this token exists, we have a function node
            \(          # literal open paren
            (\S*)       # optional argument token (characters inside parens)
            \)          # literal close paren
        )?              # the whole function-call part of the node is optional
        /?              # optional second slash
        (.*)            # page token
    ///
    */

    // What you get out of regExp.exec()
    // regExp.exec('module/node/page')
    // ["module/node/page", "module", "node", undefined, undefined, "page"]
    // regExp.exec('module/node')
    // ["module/node/page", "module", "node", undefined, undefined, ""]
    // regExp.exec('module/func()')
    // ["module/func()", "module", "func", "()", "", ""]
    // regExp.exec('module/func(args)')
    // ["module/func(args)", "module", "func", "(args)", "args", ""]

    // The arguments token is split on commas and each argument is treated as a
    // string literal. Example:
    // 'module/func(a,b,c)'
    // Results in the call
    // func('a', 'b', 'c');

    $scope.Position.prototype.stringify = function () {
        var s = this.module + '/' + this.node;
        if (this.page) {
            s = s + '/' + this.page;
        }
        return s;
    };

    $scope.Position.prototype.isHash = function () {
        // A "hash" is a displayable position within a program, i.e. one that
        // has markup associated with it. It must include a module id, a
        // segment name, and a page. For example:
        // session_1/intro/1
        // See the comments for the Position constructor above for details.
        if (this.isFunctional) {
            // Then the node is a function and this definitely isn't a hash.
            return false;
        } else {
            // This is a segment node. If it includes a page number, we can
            // display it. Otherwise not.
            return typeof this.page === 'number';
        }
    };

    // ** Module ** //

    $scope.Module = function Module(params) {
        forEach(params, function (k, v) {
            this[k] = v;
        }, this);
    };

    $scope.Module.prototype.progressVariable = function () {
        return 's' + this.activity_ordinal + '__progress';
    };

    $scope.Module.prototype.getRecentPosition = function () {
        // figure out the most recent position the user was at WITHIN THIS module
        console.debug(this.name, "getRecentPosition()");
        var recentPosition = null;
        if ($scope.pd.position_history) {
            forEach($scope.pd.position_history, function (positionString) {
                var pos = new $scope.Position(positionString);
                if (pos.module === this.id) {
                    recentPosition = pos;
                }
            }, this);
        }
        return recentPosition;
    };

    $scope.Module.prototype.runUntilHash = function (currentPosition) {
        // We might go to two places: the next node in the list, or wherever
        // the current position function points. Between the two, prefer what
        // the function says. Once we've chosen, decide if we have to keep
        // going to get to hash, or if this is one and we can stop.
        var newPosition = this.nextPosition(currentPosition);
        console.debug(this.id, "runUntilHash(), currentPosition:", (currentPosition ? '#' + currentPosition.stringify() : 'undefined'), "iterated position:", (newPosition ? '#' + newPosition.stringify() : 'undefined'));
        if (currentPosition) {
            if (currentPosition.isFunctional) {
                // functional nodes may return
                // 1) undefined - the default; just go on to the next position
                // 2) A position - so go to that position
                // 3) A promise - that means an ajax call was sent out, and we
                //    need to stop entirely, trusting to the callback to
                //    restart the flow.
                // var result = currentPosition.execute();

                var functionNode = $scope[currentPosition.functionName];
                var result = functionNode.apply(this, currentPosition.args);

                if (result instanceof $scope.Position) {
                    newPosition = result;
                    console.debug("got position from functional node=", '#' + newPosition.stringify());
                } else if (result !== undefined) {
                    // Assume result is a promise.  Restart the flow at the
                    // next node, when the ajax call returns/resolves.
                    var restart;
                    if ($scope.testing.on) {
                        restart = $scope.testRun.partial(newPosition).bind(this);
                    } else {
                        restart = this.goToNextHash.partial(newPosition).bind(this);
                    }
                    $q.when(result).then(restart);
                    console.debug("got promise from functional node, waiting...");
                    return;
                }
                // else if result === undefined then do nothing, the existing
                // value of newPosition is fine
            }
        }
        // from here we can assume we have a position to work with
        if (newPosition.isHash()) {
            return newPosition;
        } else {
            return this.runUntilHash(newPosition);
        }
    };

    $scope.Module.prototype.nextPosition = function (currentPosition) {
        // Find the next position based on the current one, regardless of
        // its validity as a hash (i.e. may be a functional node).
        // Examples:
        // #1 First node in module is functional:
        //    undefiend => module/function()
        // #2 First node is module is a segment:
        //    undefined => module/segment/1
        // #3 Same as #2 but coming from another module
        //    otherModule/whatever() => module/segment/1
        // #4 At some page in the middle of a segment
        //    module/segment/2 => module/segment/3
        // #5 At some page at the end of a segment
        //    module/segment/3 => module/branch()
        // DOES NOT HANDLE getting the next position when at the very end of
        // a module.

        console.debug(this.id, "nextPosition(), currentPosition:",
                    (currentPosition ? '#' + currentPosition.stringify() : 'undefined'));
        var newNode,
            newPosition,
            incrementPage,
            incrementNode,
            currentNodeIndex;

        if (currentPosition && currentPosition.module === this.id) {
            // First, where are we?
            currentNodeIndex = this.nodes.indexOf(currentPosition.node);

            // Now we have to determine if the next position is a PAGE within the
            // current node or we need to move to the next node (because 
            // there are no more pages here or there never were any).
            if (currentPosition.isFunctional) {
                // this is a function node, it doesn't make sense to change pages
                incrementPage = false;
            } else {
                var q = '#module_' + this.id + ' .segment[show-segment="' + currentPosition.node + '"] .page';
                var numPages = $(q).length;
                if (currentPosition.page >= numPages) {
                    // we're on the last page, can't increment
                    incrementPage = false;
                } else {
                    incrementPage = true;
                }
            }
            // if there's no page to increment, we have to go to the next node,
            // and if there IS, we can't.
            incrementNode = !incrementPage;
        } else {
            // No current position was defined, or the user is coming
            // from somewhere outside the module.
            // Create a fake position for the beginning of the module so we
            // have something to go off of.
            currentNodeIndex = -1;
            incrementNode = true;  // so we'll wind up with the 0th node
            incrementPage = false;
        }

        if (incrementPage) {
            // everything about the original position is correct, just bump up
            // the page number
            newPosition = angular.copy(currentPosition);
            newPosition.page += 1;
        } else if (incrementNode) {
            // find the node after that index
            newNode = this.nodes[currentNodeIndex + 1];
            if (!newNode) {
                // this is the end of a module
                return false;
            }
            newPosition = new $scope.Position(this.id + '/' + newNode);
            if (!newPosition.isFunctional) {
                // this is a non-function node (i.e. segment) so assume page 1
                newPosition.page = 1;
            }
        }

        return newPosition;
    };

    $scope.Module.prototype.goToNextHash = function (nextPosition) {
        console.debug(this.name, "goToNextHash(), nextPosition:", nextPosition);
        // Calling goToNextHash is the way that all modules are initiated, so
        // this is the appropriate place to record that this module is
        // active. Things like functional nodes can access this property to
        // determine what module they're running in.
        // This value is different from displayedModule, which only gets set
        // when we reach a displayable hash and controls what appears on the
        // screen.
        $scope.activeModule = this.id;
        var currentPosition;

        // It may be possible to figure out the next position immediately and
        // jump there. This may happen if the next position was passed in or
        // if we establish that the user should be directed based on their
        // position history.

        // Otherwise, we'll have to figure out the current position and use
        // runUntilHash() to start the flow, running any intermediary function
        // nodes. That will return the next position, and we'll be all set to
        // display a page to the user.

        if (nextPosition) {
            // nextPosition is optional, it's only used to restart the flow
            // after it's been stopped for an ajax callback.
            if (!nextPosition.isHash()) {
                // The place we've been asked to restart isn't a valid place
                // to stop and display, so we need to run from here.
                nextPosition = this.runUntilHash(nextPosition);
            }
            // else there's no need to start the flow, we know where to go
        } else {
            // no next position provided, we have to figure it out from the URL
            var hash = $scope.getPositionFromURL();
            var history = this.positionHistory();
            if (hash && hash.module === this.id) {
                // the user is currently somewhere in this module; use this as
                // their current position and send them to whatever is next
                nextPosition = this.runUntilHash(hash);
            } else if (history.length > 0 && this.type === 'activity') {
                // no position has been specified in the url, but
                // this user has been in this ACTIVITY before; rather than
                // starting at the beginning, jump to the last
                // point in the history within this module
                nextPosition = new $scope.Position(history[history.length - 1]);
            } else {
                // either there's no history for this module or it's not
                // relevant because this isn't an activity; start them at the
                // beginning by giving an undefined current position
                nextPosition = this.runUntilHash(undefined);
            }
        }

        // runUntilHash may have returned nothing b/c it's waiting for an
        // ajax call, so check that next position is defined before actually
        // changing the URL fragment and displaying a page.
        if (nextPosition) {
            console.debug(this.name, "goToNextHash() got nextPosition", '#' + nextPosition.stringify());
            if ($scope.testing.on) {
                $scope.testing.currentHash = nextPosition.stringify();
                // nothing's watching currentHash, so manually call the handler
                $scope.hashHandler();
            } else {
                $window.location.hash = nextPosition.stringify();
            }
        }

        // If nextPosition is undefined, do nothing. We rely on whatever ajax
        // call is pending to have registered a callback that will restart the
        // flow.
    };

    $scope.Module.prototype.display = function (segment, page) {
        console.debug(this.id + ".display()", segment, page);
        if ($scope.testing.on) {
            console.error("I don't want to reach display().");
        }
        $scope.displayedModule = this.id;
        // If the user jumped to this hash directly (e.g. via link or by
        // page refresh), they won't have gone through the module from the
        // beginning, and activeModule may not be set. So set it here also.
        $scope.activeModule = this.id;
        $scope.activeSegment = segment;
        $scope.activePage = page;
        // see issue #107
        $('#loading').addClass('program_page_loaded');
        // see issue #17
        $('body, html').animate({scrollTop: 0}, 0);
    };

    $scope.Module.prototype.positionHistory = function () {
        var history = arrayUnique(angular.copy($scope.pd.position_history));
        return forEach(history, function (hash) {
            var p = new $scope.Position(hash);
            if (p.module === this.id) {
                return hash;
            }
        }, this);
    };

    // ** Automated Testing ** //

    $scope.testing = {
        on: false,
        moduleId: '',
        makeCalls: false,
        userId: undefined,
        // will simulate the URL fragment, e.g. 'session_1/consent/1'
        currentHash: '',
        runs: 1,  // finalizeTestRun will start a new run until it has done this many
        results: [],
        //  results of tested paths 
        pathKeys: [],
        pathResults: [],
        variableResults: {}
    };

    $scope.createTestUser = function () {
        return $pertsAjax({
            url: '/api/put/user',
            params: {
                user_type: 'student',
                classroom: $window.classroomId,
                first_name: $window.programAbbreviation + ' test',
                last_name: 'student',
                is_test: true,
                escape_impersonation: true
            }
        }).then(function (response) {
            $scope.testing.userId = response.id;
        });
    };

    $scope.testRun = function (currentPosition) {
        // This is essentially a testing version of goToNextHash().
        console.debug("testRun() moduleId:", $scope.testing.moduleId, "currentPosition:", currentPosition ? '#' + currentPosition.stringify() : 'undefined');
        // Disable synchronization during the test run.
        $window.synchronization = false;
        var module = $scope.outline[$scope.testing.moduleId];
        var promise;
        if (!currentPosition) {
            // We're not restarting mid-run, so do some initialization.
            $scope.initPd();  // clear the user's data
            if ($scope.testing.makeCalls) {
                // Overwrite the dummy promise so that testing doesn't start
                // until the testing user is created.
                promise = $scope.createTestUser();
            } else {
                $scope.testing.userId = generateId('user');
                // Create and resolve the a deferred immediately to imitate the
                // createTestUser() call.
                promise = $emptyPromise();
            }
        } else if (currentPosition.isHash()) {
            // We've arrived at a page to test; hand off testing flow and stop.
            $scope.testing.currentHash = currentPosition.stringify();
            $scope.hashHandler();
            return;
        } else if (currentPosition.isFunctional) {
            // This is a function node waiting to be run. We want that to
            // happen right away, so create an immediately-resolving promise.
            promise = $emptyPromise();
        }

        promise.then(function () {
            // Here, currentPosition is either undefined or a functional node
            // either way, the right move is to pass it to runUntilHash().
            var positionOrPromise = module.runUntilHash(currentPosition);
            if (positionOrPromise instanceof $scope.Position) {
                // Since runUntilHash returned a position, we know it's a hash.
                $scope.testing.currentHash = positionOrPromise.stringify();
                $scope.hashHandler();
            }
            // Else, assume we are set to restart testing later because an ajax
            // call was encountered somewhere in runUntilHash().
        });
    };

    $scope.testPage = function (position) {
        // This is a testing version of display(). However, it doesn't stop. It
        // immediately clicks to the next page.
        $scope.testing.currentHash = position.stringify();
        if ($scope.showNextButton()) {
            console.debug("testPage()", '#' + position.stringify(), "clicking next button...");
            $scope.nextButton();
        } else {
            $scope.finalizeTestRun();
        }
    };

    $scope.finalizeTestRun = function () {
        // A test run of a module is complete.
        console.debug("finalizeTestRun(): next button not shown; assumed end of module.");
        $window.synchronization = true;
        $scope.testing.results.push($scope.pd);
        if ($scope.testing.makeCalls) {
            $scope.synchronize();
        }
        // If multiple runs were requested
        if ($scope.testing._i !== undefined) {
            // and they're not all done yet
            if ($scope.testing._i < $scope.testing.runs) {
                // then start a new run.
                $scope.testing._i += 1;
                $scope.testRun();
            } else {
                $scope.testing._deferred.resolve();
            }
        }
    };

    $scope.testModule = function () {
        $scope.testing.on = true;
        $scope.testing._i = 1;
        $scope.testing.results = [];
        $scope.testing._deferred = $q.defer();
        $scope.testRun();
        $scope.testing._deferred.promise.then(function () {
            $scope.testing.on = false;
            $scope.processTestResults();
        });
    };

    $scope.processTestResults = function () {
        forEach($scope.testing.results, function (pd) {
            var pathKeys = $scope.testing.pathKeys;
            var pathResults = $scope.testing.pathResults;
            var pathKey = pd.position_history.toString();
            if (pathKeys.indexOf(pathKey) === -1) {
                pathKeys.push(pathKey);
                pathResults[pathKeys.indexOf(pathKey)] = pd;
                pathResults[pathKeys.indexOf(pathKey)].count = 0;
            }
            pathResults[pathKeys.indexOf(pathKey)].count += 1;
        });
    };


    // ** onPageLoad Functions ** //


    $scope.getPd = function (scope) {
        var params = {program: $window.programId};

        if (scope === 'user') {
            params.scope = $window.userId;
        } else if (scope === 'classroom') {
            params.scope = $window.classroomId;
        } else if (scope === 'cohort') {
            params.scope = $window.cohortId;
        }
        // Enables strongly consistent ancestor queries.
        params.ancestor = params.scope;
        
        // $pertsAjax uses deferreds and returns promises. Deferreds offer a
        // way to track when asynchronous functions return. We'll return a
        // promise from this deferred immediately, and later, when the  ajax
        // callback executes, we'll resolve the same deferred. Other code using
        // the returned promise will then be able to detect that this deferred
        // has resolved.
        // See http://markdalgleish.com/2013/06/using-promises-in-angularjs-views/
        return $pertsAjax({
            url: '/api/get/pd',
            // provie the minimal parameters so that we get everything
            params: params
        }).then(function (response) {
            // separate the list of pd's by scope
            // make sure to update both the main data model and the cache
            // so that synchronize() doesn't think that this data needs to
            // be sent back to the server again
            var model, cache;
            if (scope === 'user') {
                model = $scope.pd;
                cache = $scope.caches.pd.cache;
            } else if (scope === 'classroom') {
                model = $scope.classroomPd;
                cache = $scope.caches.classroomPd.cache;
            } else if (scope === 'cohort') {
                model = $scope.cohortPd;
                cache = $scope.caches.cohortPd.cache;
            }
            var jsonVariables = ['position_history'];
            forEach(response, function (pd) {
                var value = pd.value;
                if (arrayContains(jsonVariables, pd.variable)) {
                    value = JSON.parse(pd.value);
                }
                cache[pd.variable] = angular.copy(value);
                model[pd.variable] = angular.copy(value);
                // Save progress data in a special location so we can determine
                // WHEN users last submitted data.
                if (pd.variable.contains('__progress')) {
                    $scope.progressDates[pd.variable] = Date.createFromString(pd.created, 'UTC');
                }
            });
        });
    };

    $scope.getActivities = function (userType) {
        var params = {
            user_type: userType,
            assc_program_list: $window.programId,
            assc_cohort_list: $window.cohortId
        };
        if ($window.subprogram === 'student') {
            params.assc_classroom_list = $window.classroomId;
        }
        return $pertsAjax({
            url: '/api/get/activity',
            params: params
        }).then(function (response) {
            // Match up activities with their corresponding normal and
            // alternale modules, storing the activity id for future pd puts.
            var acts = response;  // activities
            forEach(acts, function (activity) {
                forEach($scope.outline, function (id, module) {
                    if (
                        (module.type === 'activity' || module.type === 'alternate') &&
                        module.activity_ordinal === activity.activity_ordinal
                    ) {
                        module.activity_id = activity.id;
                    }
                });
            });
        });
    };

    // ** Functions ** //

    // https://coderwall.com/p/ngisma
    // For when a funtion might be called in $scope, and it might be called
    // out of $scope. Checks whether an $apply() is required before doing it.
    $scope.$safeApply = function (fn) {
        var phase = this.$root.$$phase;
        if (phase === '$apply' || phase === '$digest') {
            if (fn && (typeof fn === 'function')) {
                fn();
            }
        } else {
            this.$apply(fn);
        }
    };

    $scope.hashHandler = function () {
        // Watch for when the hash (url framgent) changes and then fires the
        // correct controller; uses jQuery.
        var pos = $scope.getPositionFromURL();
        if (pos) {
            var posStr = pos.stringify();
            console.debug("detected hash change:", '#' + posStr);
            if (!arrayContains($scope.pd.position_history, posStr)) {
                $scope.pd.position_history.push(pos.stringify());
            }
            // check it against each module
            forEach($scope.outline, function (moduleId, module) {
                if (moduleId === pos.module) {
                    // this is the right kind of hash for this module, so get
                    // the arguments in the hash (if they exist), and call the
                    // module's controller
                    if ($scope.testing.on) {
                        $scope.testPage(pos);
                    } else {
                        module.display(pos.node, pos.page);
                    }
                }
            });
        } else {
            // the hash didn't match any of the modules
            // or the user returned to an empty hash (no url fragment)
            // todo: consider putting a 404-like message here
            window.onerror("404: unknown position: " + $window.location.hash);
        }
    };

    $scope.initPd = function () {
        $scope.pd = {
            position_history: []
        };
        $scope.classroomPd = {};
        $scope.cohortPd = {};

        // used for synchronization
        $scope.caches = {
            'pd': {
                'cache': {},
                'pdScope': 'user'
            },
            'classroomPd': {
                'cache': {},
                'pdScope': 'classroom'
            },
            'cohortPd': {
                'cache': {},
                'pdScope': 'cohort'
            }
        };
    };

    $scope.beginFlow = function () {
        console.debug("beginFlow()");
        // Start synchronizing data with the server every few seconds. Use a
        // slightly longer time period that the minimum put interval, otherwise
        // we'd get throttled all the time.
        var interval = $scope.minPutInterval + 500;
        // setInterval($scope.$apply($scope.synchronize), interval);
        setInterval($scope.synchronize, interval);

        // Data collection is done; figure out where to send them.
        if ($window.location.hash) {
            // There's a hash in the URL.
            $scope.hashHandler();
        } else {
            // There's no hash yet; assume the start module and start the flow.
            $scope.outline.start.goToNextHash();
        }
    };

    $scope.getPositionFromURL = function () {
        // During testing, this checks a fake hash set in the testing object
        // rather than the URL fragment so we can simulate moving to different
        // hashes.
        var hash = $scope.testing.on ?
                    $scope.testing.currentHash :
                    $window.location.hash.substring(1);
        if (hash) {
            var pos = new $scope.Position(hash);
            if (!pos || !pos.isHash()) {
                throw new Error("Invalid position in hash.");
            }
            return pos;
        } else {
            return null;
        }
    };

    $scope.batchPutPd = function (pdBatch, scope) {
        // Send a list of pd ("program data") to the server.

        // Don't bother with empty change sets.
        if (pdBatch.length === 0) { return $emptyPromise(); }

        // But we only support user-scope pds right now. It's not clear what
        // properties we would require on classroom- or cohort-scope pd, or who
        // would have the permission to write them.
        if (scope !== 'user') {
            throw new Error("Unsupported pd scope: " + scope);
        }

        var module = $scope.outline[$scope.activeModule];
        // Activity id not used in Yosemite. Along with cohort and classroom,
        // not using this relationship makes it easier to re-associate users
        // without mangling their data.
        // var activity_id = module ? module.activity_id : null;
        var activity_ordinal = module ? module.activity_ordinal : null;
        var params = {
            pd_batch: pdBatch,
            activity_ordinal: activity_ordinal,
            program: $window.programId,
            scope: $scope.testing.on ? $scope.testing.userId : $window.userId,
            is_test: $scope.testing.on
        };

        var pdName;
        if (scope === 'user') {
            params.scope = $scope.testing.on ? $scope.testing.userId : $window.userId;
            pdName = 'pd';
        } else if (scope === 'classroom') {
            params.scope = $window.classroomId;
            pdName = 'classroomPd';
        } else if (scope === 'cohort') {
            params.scope = $window.cohortId;
            pdName = 'cohortPd';
        }

        return $pertsAjax({
            url: '/api/batch_put_pd',
            method: 'POST',
            params: params
        }).then(function successCallback(response) {
            // We know the server heard us, so change the cache, which is the
            // client's model of what the server knows.
            forEach(response, function (pd) {
                $scope.caches[pdName].cache[pd.variable] = angular.copy(
                    $scope[pdName][pd.variable]);
            });
        });
    };

    $scope.putPd = function (variable, value, scope) {
        // Send pd ("program data") to the server. The last three arguments
        // are optional. The last two are only used for automated testing.
        var module = $scope.outline[$scope.activeModule];
        // Activity id not used in Yosemite. Along with cohort and classroom,
        // not using this relationship makes it easier to re-associate users
        // without mangling their data.
        // var activity_id = module ? module.activity_id : null;
        var activity_ordinal = module ? module.activity_ordinal : null;
        var params = {
            variable: variable,
            value: value,
            activity_ordinal: activity_ordinal,
            program: $window.programId,
            is_test: $scope.testing.on
        };

        var pdName;
        if (scope === 'user') {
            params.scope = $scope.testing.on ? $scope.testing.userId : $window.userId;
            pdName = 'pd';
        } else if (scope === 'classroom') {
            params.scope = $window.classroomId;
            pdName = 'classroomPd';
        } else if (scope === 'cohort') {
            params.scope = $window.cohortId;
            pdName = 'cohortPd';
        }

        return $pertsAjax({
            url: '/api/put/pd',
            method: 'POST',
            params: params
        }).then(function successCallback() {
            // We know the server heard us, so change the cache, which is the
            // client's model of what the server knows.
            $scope.caches[pdName].cache[variable] = angular.copy(
                $scope[pdName][variable]);
        });
    };

    $scope.stratify = function (stratifier_name, attributes) {
        // This is called from functional nodes, and so must be able to silence
        // itself during testing if makeCalls is false.
        if ($scope.testing.on && $scope.testing.makeCalls === false) {
            var group = clientRandomizer(stratifier_name);
            // Imitate the promise a real call to stratify would produce.
            return $emptyPromise(group);
        } else {
            return $pertsAjax({
                url: '/api/stratify',
                params: {
                    name: stratifier_name,
                    program: $window.programId,
                    proportions: $window.configJson.stratifiers[stratifier_name],
                    attributes: attributes
                }
            });
        }
    };

    // Synchronizes the client data model with the server.
    // Called in three cases:
    // 1. Every two seconds via a setInterval in beginFlow().
    // 2. Also when the user clicks the next button.
    // 3. During testing if makeCalls is true. Then it's called once at the end
    //    of each run.
    $scope.synchronize = function (force) {
        // This function self-regulates how often it can execute, but you can
        // force it to execute.
        force = force === true;

        if ($window.synchronization === true) {
            console.debug("synchronize(), force:", force);
        } else {
            console.debug('synchronization is off');
            return;
        }

        var promises = [];

        // for each pd scope (user, classroom, cohort)
        forEach($scope.caches, function (pdName, cache) {
            var scope = cache.pdScope;

            // Check when this scope was last updated, and if it was updated
            // too recently, skip it.
            var now = new Date();
            if ($scope.putTimes[scope] instanceof Date && !force &&
                now - $scope.putTimes[scope] < $scope.minPutInterval) {
                // Exit the forEach loop, which is just a function.
                // This data will be put in a future synchronize() call.
                return;
            } else {
                $scope.putTimes[scope] = now;
            }

            // collect all the changes into a single list
            var pdBatch = [];
            var toUpdate = dictionaryDiff($scope[pdName], cache.cache);
            forEach(toUpdate, function (key) {
                if ($scope[pdName][key] === undefined) {
                    throw new Error(pdName + '.' + key + ' not defined.');
                }
                pdBatch.push({
                    variable: key,
                    value: $scope[pdName][key]
                });
            });

            // If there are no pds to save, don't attempt to put them.
            if (pdBatch.length === 0) { return; }

            // Now that all the pd changes have been collected into a batch,
            // send them to the server.
            var p = $scope.batchPutPd(pdBatch, scope).then(function successCallback() {
                // Erase any problems they had before, connection is working now.
                $scope.failedPdPuts = 0;
            }, function errorCallback(exception) {
                console.debug("sync error callback, force: ", force, "failed puts:", $scope.failedPdPuts);
                // Don't change the cache, b/c the call likely wasn't successful.
                // Track how many failed attempts there are, so we can eventually
                // help the user out.
                $scope.failedPdPuts += 1;
                if ($scope.failedPdPuts <= $scope.pdPutRetries) {
                    if (force) {
                        console.debug("sync retrying immediately because " +
                            "force is set to true", $scope.failedPdPuts,
                            $scope.pdPutRetries, force);
                        // Important to return the promise here, so the program
                        // continues to wait for a successful synchronize.
                        return $scope.synchronize(force);
                    }
                    console.debug("sync doing nothing b/c force not set to " +
                        "true. We'll try again later.");
                    // Do nothing. Just wait for sync to be called again.
                } else {
                    // If the user really can't seem to reach the server, redirect
                    // them to login and send an error to Sentry and the app engine logs.
                    $window.onerror("User data synchronization failed: " + exception);
                    $scope.handleDisconnectedUser(
                        "We are having trouble saving your responses.");
                }
            });
            promises.push(p);
        });
        // Send back a promise that will resolve when all the saving is done.
        return $q.all(promises);
    };

    $scope.previousButton = function () {
        var currentPosition = $scope.getPositionFromURL();
        var module = $scope.outline[currentPosition.module];
        var modHistory = module.positionHistory();
        var modOrdinal;
        var prevHash;
        modOrdinal = modHistory.indexOf(currentPosition.stringify());
        if (modOrdinal > 0) {
            prevHash = modHistory[modOrdinal - 1];
        } else {
            prevHash = modHistory[0];
        }
        $window.location.hash = prevHash;
    };

    $scope.nextButton = function () {
        console.debug("nextButton()");
        $scope.synchronize();
        var pos = $scope.getPositionFromURL();
        var module = $scope.outline[pos.module];
        module.goToNextHash();
    };

    $scope.showPreviousButton = function () {
        var pos = $scope.getPositionFromURL();
        var validPosition = Boolean(pos);
        var manuallyDisabled = false;
        if (pos) {
            manuallyDisabled = arrayContains($scope.hideButton.previous, pos.stringify());
        }
        return validPosition && !manuallyDisabled;
    };

    $scope.showNextButton = function () {
        var pos = $scope.getPositionFromURL();
        var validPosition = Boolean(pos);
        var endOfModule = false;
        var manuallyDisabled = false;
        if (pos) {
            var module = $scope.outline[pos.module];
            endOfModule = module.nextPosition(pos) === false;
            manuallyDisabled = arrayContains($scope.hideButton.next, pos.stringify());
        }
        return validPosition && !endOfModule && !manuallyDisabled;
    };

    $scope.handleDisconnectedUser = function (reason) {
        // Reason should be human readable so that users can report the problem
        // to us easily. It should be a sentence or sentences and end in a
        // period.

        // Don't let the user leave the page to go to Qualtrics.
        $scope.allowRedirect = false;

        // Send an error to Sentry and the app engine logs.
        $window.onerror(reason);

        // Notify the user.
        alert(reason + "\n\nThis page will refresh. If you continue to have " +
              "problems, please log out and log in again.");

         // Refresh the page; users will be brought back to the current hash.
         $window.location.reload();
    };

    // ** Events ** //


    $scope.onPageLoad = function () {
        console.debug("onPageLoad()");

        $window.initAutoHide();

        // clear/set-up pd objects
        $scope.initPd();

        $($window).hashchange(function () {
            $scope.$safeApply($scope.hashHandler);
        });

        if ($scope.testing.on) {
            // Don't get user data from the server, and don't begin the flow,
            // the testing framework will take over instead.
            return;
        }

        // This is a set of async calls that load all the data about the user
        // necessary to get started. We can't actually start running the app
        // until it has all arrived b/c where the user goes depends on the
        // data. So set up a promise that will be able to tell when they're
        // all done and THEN start the flow.
        // see http://markdalgleish.com/2013/06/using-promises-in-angularjs-views/
        // and http://docs.angularjs.org/api/ng.$q
        //
        // The calls are organized by 'scope', which is "who/what the pds are
        // about". For instance, facts about users (like this user has done 50%
        // of the session) are user scope. Facts about classrooms (like the
        // whole classroom has been assigned a condition) are classroom scope.
        // Classroom scope pds only make sense in the student subprogram,
        // because teachers may own several classrooms.
        var promises;
        if ($window.subprogram === 'student') {
            promises = [
                // In Yosemite we don't use the activity ids to record data,
                // so there's no need to fetch them.
                // $scope.getActivities($window.userType),
                $scope.getPd('user'),
                $scope.getPd('classroom'),  // for students, this makes sense
                $scope.getPd('cohort')
            ];
        } else if ($window.subprogram === 'teacher') {
            promises = [
                // In Yosemite we don't use the activity ids to record data,
                // so there's no need to fetch them.
                // $scope.getActivities($window.userType),
                $scope.getPd('user'),
                $scope.getPd('cohort')
            ];
        } else {
            throw new Error("Unknown subprogram: (" +
                typeof $window.subprogram + ") " + $window.subprogram);
        }
        $q.all(promises).then($scope.beginFlow);
    };

    // ** Main ** //

    // process the static config data into an outline of Module objects
    $scope.staticOutline = $window.configJson.outline;
    $scope.outline = {};
    forEach($scope.staticOutline, function (moduleParams) {
        $scope.outline[moduleParams.id] = new $scope.Module(moduleParams);
    });

    // create a place to store when progress pds were recorded
    $scope.progressDates = {};

    // individual pages can add themselves to this list to turn off nav buttons
    $scope.hideButton = {next: [], previous: []};
}

function watchShowAll(s, e) {
    'use strict';
    s.$watch('showAll', function (value) {
        if (value) {
            e.addClass('show-all');
        } else {
            e.removeClass('show-all');
        }
    });
}


PertsApp.directive('showModule', function () {
    'use strict';
    return function postLink(scope, element, attributes) {
        element.addClass('module');
        // The value of the attribute is available, in raw form (the exact
        // string btwn the double quotes in the html) as attributes.showModule.
        // Using scope.$eval on it is what angular normally does, but for this
        // purpose, a raw string is fine.
        var moduleId = attributes.showModule;
        // Then, we get ready for the displayed module to change
        scope.$watch('displayedModule', function (value) {
            // and show/hide it based on whether it matches what is specified
            // for this particular element
            if (value === moduleId) {
                // element is a jQuery-like result set
                element.removeClass('ng-hide');
            } else {
                element.addClass('ng-hide');
            }
        });
        watchShowAll(scope, element);
    };
});

PertsApp.directive('showSegment', function () {
    'use strict';
    return function postLink(scope, element, attributes) {
        element.addClass('segment');
        var segment = attributes.showSegment;
        scope.$watch('activeSegment', function (value) {
            if (value === segment) {
                element.removeClass('ng-hide');
            } else {
                element.addClass('ng-hide');
            }
        });
        watchShowAll(scope, element);
    };
});

PertsApp.directive('showPage', function () {
    'use strict';
    return function postLink(scope, element, attributes) {
        element.addClass('page');  // for styling

        // determine page number by position in markup, store as data attribute
        var pageNum;
        if (element.data('page') === undefined) {
            $('*[show-page]', element.parent()).each(function (index, el) {
                if (el === element[0]) {
                    pageNum = index + 1;
                    element.data('page', pageNum);
                }
            });
        }

        // Create an informative visual divider between pages that is seen only
        // on show-all.
        var segment = element.parent().attr('show-segment');
        var module = element.parent().parent().attr('show-module');
        element.before(
            '<div class="page_divider">' +
                '<hr>' +
                '<pre>' + module + ' > ' + segment + ' > page ' + pageNum + '</pre>' +
            '</div>'
        );

        // For normal viewing, hide all pages but the active one.
        scope.$watch('activePage', function (value) {
            if (value === element.data('page')) {
                element.removeClass('ng-hide');
            } else {
                element.addClass('ng-hide');
            }
        });
        watchShowAll(scope, element);
    };
});

PertsApp.directive('hidePreviousButton', function () {
    'use strict';
    return function postLink(scope, element, attributes) {
        if (!scope.hideButton) {
            scope.hideButton = {next: [], previous: []};
        }
        scope.hideButton.previous.push(attributes.hidePreviousButton);
    };
});

PertsApp.directive('hideNextButton', function () {
    'use strict';
    return function postLink(scope, element, attributes) {
        if (!scope.hideButton) {
            scope.hideButton = {next: [], previous: []};
        }
        scope.hideButton.next.push(attributes.hideNextButton);
    };
});