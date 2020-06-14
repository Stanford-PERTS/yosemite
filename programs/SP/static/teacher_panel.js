/* make JSLint complain less */
/*jslint browser: true*/
/*globals alert, confirm, prompt, console, $, jQuery, angular, forEach*/
/*globals noop, PertsApp, arrayUnique, arrayContains, initProp, queryString*/
/*globals datepickr*/

function getScope() {
    'use strict';
    return angular.element($('#scope').get()).scope();
}

function CohortChooserController($scope, $pertsAjax, $window) {
    'use strict';
    $scope.cohortList = $pertsAjax({url: '/api/get/cohort'}).then(function (response) {
        if (response.length === 1) {
            $scope.selectedCohortId = response[0].id;
            $scope.choose();
        } else {
            angular.element("#cohort_chooser").show();
        }
        return response;
    });
    $scope.choose = function () {
        $window.location.href = '/p/SP/teacher_panel?cohort=' +
            $scope.selectedCohortId;
    };
}

function TeacherPanelController($scope, $pertsAjax, $getStore, $q, $emptyPromise, $window, $timeout) {
    'use strict';

    ////////    DATA INITIALIZATION

    // put the program config in root, because that also works with the dashboard
    $scope.$root.programOutline = $window.programOutline;

    // put the pd json dump in the store and index by variable name
    $scope.pd = {};
    forEach($getStore.setList($window.pd), function (pd) {
        $scope.pd[pd.variable] = pd;
    });
    if ($scope.pd.condition) {
        $scope.$root.conditionPd = $scope.pd.condition;
    }
    var cohortId = queryString('cohort');
    $getStore.load([$window.userId, $window.programId, cohortId]);
    $scope.user = $getStore.get($window.userId);
    $scope.program = $getStore.get($window.programId);
    $scope.cohort = $getStore.get(cohortId);
    $scope.steps = [];
    $scope.stepCounter = 1;

    // activity calendars will copy their dates into here, allowing other
    // calendars to disable their dates in response to others
    $scope.scheduleConstraints = {};

    $pertsAjax({url: '/api/get/classroom'}).then(function (response) {
        $scope.classroomList = $getStore.setList(response);
    });

    $scope.$on('/classroomCreator/classroomAdded',
               function (event, teacherId, classroomId, activityIds) {
        $scope.classroomList.push($getStore.get(classroomId));
        // bounce the publication back down to children (e.g. scheduling
        // widgets, which need the new student activities)
        $scope.$broadcast('/teacherPanel/classroomAdded', activityIds);
    });

    ////////    STEP DEFINITIONS

    var Step = function (ordinal, params) {
        this.ordinal = ordinal;
        forEach(params, function (k, v) {
            this[k] = v;
        }, this);
        initProp(this, 'init', noop);
        this.init();
    };

    Step.prototype.completionPd = function () {
        var pd = $scope.pd['checklist-teacher-' + this.ordinal];
        if (pd) {
            return pd;
        } else {
            return {value: 'false'};
        }
    };

    Step.prototype.isComplete = function () {
        return this.completionPd().value === 'true';
    };

    Step.prototype.markAsComplete = function () {
        this.completionPd().value = 'true';  // string, not boolean!
    };

    Step.prototype.invalidMessage = function () { return ''; };

    Step.prototype.cssClasses = function () {
        var c = this.isComplete();
        var a = this.isAvailable();
        return {
            complete: c,
            available: a,
            disabled: !a,
            active: this.active
        };
    };

    Step.prototype.iconClasses = function () {
        var c = this.isComplete();
        return {
            "icon-li": true,
            "icon-check": c,
            "icon-check-empty": !c
        };
    };

    // called from clicks on collapsed accordions; changes hash (maybe)
    Step.prototype.open = function () {
        if (this.isAvailable()) {
            $scope.goToOrdinal(this.ordinal);
        }
    };

    // educator agreement

    $scope.steps[1] = new Step(1, {
        title: "Agreement",
        isAvailable: function () {
            return true;
        },
        isValid: function () {
            if (!$scope.pd.educator_agreement_accepted) {
                return true;
            }
            var pdId = $scope.pd.educator_agreement_accepted.id;
            var pd = $getStore.get(pdId);
            if (pd.value === 'true') {
                this.invalidMessage = function () {
                    return "You have accepted the agreement.";
                };
                return false;
            } else {
                return true;
            }
        },
        next: function () {
            var pdId = $scope.pd.educator_agreement_accepted.id;
            var pd = $getStore.get(pdId);
            pd.value = 'true';
            this.markAsComplete();
            $scope.goToOrdinal(2);
        }
    });

    // add classrooms

    $scope.steps[2] = new Step(2, {
        title: "My Classes",
        invalidMessage: function () {
            if (this.isComplete()) {
                return "Manage your classes.";
            } else {
                return "Please add your classes.";
            }
        },
        isAvailable: function () {
            // step 1 must be done
            return $scope.steps[1].isComplete();
        },
        isValid: function () {
            if ($scope.classroomList) {
                return $scope.classroomList.length >= 1;
            } else {
                return false;
            }
        },
        next: function () {
            this.markAsComplete();
            $scope.goToOrdinal(3);
        }
    });

    // schedule student sessions

    $scope.steps[3] = new Step(3, {
        title: "Schedule Classes",
        init: function () {
            var _this = this;
            $scope.$on('teacherScheduling/allScheduled/student', function () {
                _this.valid = true;
            });
        },
        invalidMessage: function () {
            if (this.isComplete()) {
                return "You have scheduled all your classes.";
            } else {
                return "Please schedule all your classes.";
            }
        },
        isAvailable: function () {
            return $scope.steps[2].isComplete();
        },
        isValid: function () {
            return this.valid;
        },
        next: function () {
            if (!$scope.pd.condition || !$scope.pd.condition.value) {
                // teacher doesn't yet have a condition, need to stratify
                $scope.stratifyTeacher();
            }
            this.markAsComplete();
            $scope.goToOrdinal(4);
        }
    });

    // schedule teacher sessions

    $scope.steps[4] = new Step(4, {
        title: "Schedule Teacher Sessions",
        init: function () {
            var _this = this;
            $scope.$on('teacherScheduling/allScheduled/teacher', function () {
                _this.valid = true;
            });
        },
        invalidMessage: function () {
            if (this.isComplete()) {
                return "You have scheduled all your sessions.";
            } else {
                return "Please schedule all your sessions.";
            }
        },
        isAvailable: function () {
            return $scope.steps[3].isComplete();
        },
        isValid: function () {
            return this.valid;
        },
        next: function () {
            this.markAsComplete();
            $scope.goToOrdinal(5);
        },
        isControl: function () {
            if ($scope.pd.condition) {
                if ($scope.pd.condition.value === "control") {
                    return true;
                }
            } else {
                return false;
            }
        },
        isTreatment: function () {
            if ($scope.pd.condition) {
                if ($scope.pd.condition.value === "treatment") {
                    return true;
                }
            } else {
                return false;
            }
        }
    });

    //  parent info confirmation

    $scope.steps[5] = new Step(5, {
        title: "Parent Letter",
        isAvailable: function () {
            return $scope.steps[4].isComplete();
        },
        isValid: function () {
            if (!$scope.pd.parent_info_confirmed) {
                return true;
            }
            var pdId = $scope.pd.parent_info_confirmed.id;
            var pd = $getStore.get(pdId);
            if (pd.value === 'true') {
                this.invalidMessage = function () {
                    return "You have confirmed the parent letters were sent home.";
                };
                return false;
            } else {
                return true;
            }
        },
        next: function () {
            var pdId = $scope.pd.parent_info_confirmed.id;
            var pd = $getStore.get(pdId);
            pd.value = 'true';
            this.markAsComplete();
            $scope.goToOrdinal(6);
        }
    });

    // student session 1

    $scope.steps[6] = new Step(6, {
        title: "Student Session 1",
        invalidMessage: function () {
            if (this.isComplete()) {
                return "You reported this session was completed.";
            } else {
                return "Please bring your students to the lab.";
            }
        },
        isAvailable: function () {
            return $scope.steps[5].isComplete();
        },
        isValid: function () {
            return !this.isComplete();
        },
        next: function () {
            this.markAsComplete();
            $scope.goToOrdinal(7);
        }
    });

    // teacher program

    $scope.steps[7] = new Step(7, {
        title: "Teacher Program",
        teacherProgramLink: '/p/SP/teacher?cohort=' + $scope.cohort.id,
        invalidMessage: function () {
            if (this.isComplete()) {
                return "You completed all your sessions.";
            } else {
                return "Please complete all your sessions.";
            }
        },
        isAvailable: function () {
            // must have scheduled all teacher sessions
            return $scope.steps[6].isComplete();
        },
        isValid: function () {
            return !this.isComplete();
        },
        next: function () {
            this.markAsComplete();
            $scope.goToOrdinal(8);
        }
    });

    // student sessions 2

    $scope.steps[8] = new Step(8, {
        title: "Student Session 2",
        invalidMessage: function () {
            if (this.isComplete()) {
                return "Thank you! You are done with the SP Program.";
            } else {
                return "Please bring your students to the lab.";
            }
        },
        isAvailable: function () {
            // must have completed all teacher sessions
            return $scope.steps[7].isComplete();
        },
        isValid: function () {
            return !this.isComplete();
        },
        next: function () {
            this.markAsComplete();
            console.warn("all done! what next?");
        }
    });

    ////////    FUNCTIONS

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

    $scope.getOrdinalFromHash = function () {
        var matches = /#\/?(\d)/.exec($window.location.hash);
        if (matches && matches[1]) {
            return +matches[1];
        } else {
            return null;
        }
    };

    $scope.goToOrdinal = function (ordinal) {
        $window.location.hash = ordinal;
    };

    $scope.hashHandler = function () {
        // Watch for when the hash (url framgent) changes and then fires the
        // correct controller; uses jQuery.
        $('body, html').animate({scrollTop: 0}, 0);
        $scope.$broadcast('open_step', $scope.getOrdinalFromHash());
    };

    $scope.getFirstIncompleteOrdinal = function () {
        var o, found = false;
        forEach($scope.steps, function (step) {
            if (found) {
                return;
            } else if (!step.isComplete()) {
                o = step.ordinal;
                found = true;
            }
        });
        return o || $scope.steps.length - 1;
    };

    $scope.stratifyTeacher = function () {
        var stratifierName = 'teacher_condition';

        if ($scope.pd.condition) {
            return $emptyPromise($scope.pd.condition);
        }

        // Be flexible about the presence of attributes as we develop
        // @todo: we probably want to insist on the presence of these in the
        // future.
        var attributes = {};
        if ($scope.pd.race) {
            attributes.race = $scope.pd.race.value;
        }
        if ($scope.pd.gender) {
            attributes.gender = $scope.pd.gender.value;
        }
        return $pertsAjax({
            url: '/api/stratify',
            params: {
                name: stratifierName,
                program: $scope.program.id,
                proportions: $window.stratifier,
                attributes: attributes
            }
        }).then(function (response) {
            return $scope.putPd('condition', response).then(function (response) {
                var linkedPd = $getStore.set(response);
                $scope.pd.condition = linkedPd;
                $scope.$root.conditionPd = linkedPd;
            });
        });
    };

    $scope.putPd = function (variable, value) {
        // Makes many simplifying assumptions about appropriate values b/c this
        // is only used for a teacher outside of an activity.
        return $pertsAjax({
            url: '/api/put/pd',
            params: {
                variable: variable,
                value: value,
                activity: null,
                activity_ordinal: null,
                cohort: $scope.cohort.id,
                program: $scope.program.id,
                scope: 'user',
                user: $scope.user.id
            }
        });
    };

    $scope.initializePd = function () {
        // collect all the variables that should be initialized
        var variables = forEach($scope.steps, function (step) {
            return 'checklist-teacher-' + step.ordinal;
        }).concat(['educator_agreement_accepted',
                   'parent_info_confirmed']);
        var pdBatch = forEach(variables, function (v) {
            return {variable: v, value: false};
        });

        // put them all
        return $pertsAjax({
            url: '/api/batch_put_pd',
            method: 'POST',
            params: {
                pd_batch: pdBatch,
                user: $scope.user.id,
                program: $scope.program.id,
                cohort: $scope.cohort.id,
                scope: 'user'
            }
        }).then(function (response) {
            var pdList = $getStore.setList(response);
            $scope.pd = [];
            forEach(pdList, function (pd) {
                $scope.pd[pd.variable] = pd;
            });
        });
    };

    $scope.onPageLoad = function () {
        $($window).hashchange(function () {
            $scope.$safeApply($scope.hashHandler);
        });


        // make sure all expected pd values are here
        var x, allPdExist = true;
        // the < here is on purpose; this list starts with undefined at index
        // zero, so the length is off by one
        for (x = 1; x < $scope.steps.length; x += 1) {
            if ($scope.pd['checklist-teacher-' + x] === undefined) {
                allPdExist = false;
            }
        }
        if ($scope.pd.educator_agreement_accepted === undefined) {
            allPdExist = false;
        }
        if ($scope.pd.parent_info_confirmed === undefined) {
            allPdExist = false;
        }
        var promise = $emptyPromise();
        if (!allPdExist) {
            promise = $scope.initializePd();
        }

        promise.then(function () {
            // timeouts force an exit from the current $digest loop
            // and avoids a related error
            if (!$scope.getOrdinalFromHash()) {
                var ordinal = $scope.getFirstIncompleteOrdinal();
                $timeout($scope.goToOrdinal.partial(ordinal), 1);
            } else {
                $timeout($scope.hashHandler, 1);
            }
        });
    };
}

PertsApp.directive('step', function () {
    'use strict';
    return {
        scope: {},
        link: function (scope, element, attrs) {
            // triggered by hashHandler; either close our open yourself based
            // on the current hash
            scope.$on('open_step', function (event, ordinal) {
                if (ordinal === scope.ordinal) {
                    scope.step.active = true;
                    element.removeClass('ng-hide');
                } else {
                    scope.step.active = false;
                    element.addClass('ng-hide');
                }
            });
        },
        controller: function ($scope) {
            $scope.ordinal = $scope.$parent.stepCounter;
            $scope.$parent.stepCounter += 1;
            $scope.step = $scope.$parent.steps[$scope.ordinal];
        }
    };
});

PertsApp.directive('teacherScheduling', function () {
    'use strict';
    return {
        scope: {
            userType: '@userType'
        },
        link: function (scope, element, attr) {
            scope.sortBy = sortByFactory(scope, $('table', element).get(0), 'tr');
        },
        controller: function ($scope, $seeStore, $getStore, $pertsAjax, $window, $timeout) {
            $scope.teacher = $getStore.get($window.userId);

            // Also pre-load all associated cohorts and classrooms (needed
            // for adding displaying classroom and cohort names in
            // teacher_progess widgets).
            $scope.$watch('teacher', function (t) {
                if (t.name) {
                    var loadIds = [];
                    loadIds = loadIds.concat(t.assc_cohort_list);
                    loadIds = loadIds.concat(t.owned_classroom_list);
                    $seeStore.load(arrayUnique(loadIds));
                }
            }, true);

            $scope.fetchActivities = function (userType) {
                // pre-load all the activities these teachers have
                $pertsAjax({
                    url: '/api/get/activity',
                    params: {
                        teacher: $scope.teacher.id,
                        user_type: userType
                    }
                }).then(function (response) {
                    $scope.activityList = $getStore.setList(response);
                    $scope.$on('activitySchedule/scheduled', $scope.checkIfAllScheduled);
                    $scope.$watch('$root.conditionPd', $scope.hideTreatmentActivities);
                    // @todo: kill this hack!
                    // http://stackoverflow.com/questions/20056835/how-to-sort-child-directives-on-dynamic-values
                    if (userType === 'student') {
                        $timeout(function () { $scope.sortBy(0); }, 1);
                    }
                });
            };

            $scope.$watch('userType', $scope.fetchActivities);
            $scope.$on('/teacherPanel/classroomAdded', function (event, activityIds) {
                if ($scope.userType === 'student') {
                    forEach(activityIds, function (id) {
                        $scope.activityList.push($getStore.get(id));
                    });
                }
            });

            $scope.checkIfAllScheduled = function () {
                var allScheduled = true;
                forEach($scope.activityList, function (activity) {
                    if (!activity.scheduled_date) {
                        allScheduled = false;
                    }
                });
                if (allScheduled) {
                    $scope.$emit('teacherScheduling/allScheduled/' + $scope.userType);
                }
            };

            $scope.hideTreatmentActivities = function (conditionPd) {
                if (!conditionPd) { return; }
                var updatedList = [];
                forEach($scope.activityList, function (activity) {
                    var shouldHide = activity.user_type === 'teacher' &&
                        2 <= activity.activity_ordinal  &&
                        4 >= activity.activity_ordinal  &&
                        conditionPd.value === 'control';
                    if (shouldHide) {
                        activity.status = 'complete';
                    } else {
                        updatedList.push(activity);
                    }
                });
                $scope.activityList = updatedList;
            };
        },
        templateUrl: '/static/dashboard_widgets/teacher_scheduling.html'
    };
});

PertsApp.run(function ($seeStore, $getStore) {
    'use strict';
    // Runs every second, sends /api/put calls for updated entities.
    $getStore.watchForUpdates();
    $seeStore.watchForUpdates();
});
