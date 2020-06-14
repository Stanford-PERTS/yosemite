// Contains defintions for all the widgets (angular directives) that drive
// the dashboard.

// x = 1, y = 5, returns '20%'
// x = 1, y = 0, returns '--'
PertsApp.factory('$getPercentString', function () {
    'use strict';
    return function (x, y, divideByZeroValue) {
        if (divideByZeroValue === undefined) { divideByZeroValue = '--'; }
        return y > 0 ? Math.round(x / y * 100) + '%' : divideByZeroValue;
    };
});

function DashboardController($scope, $q, $routeParams, $emptyPromise, $location, $window, $getStore, $pertsAjax) {
    'use strict';
    $scope.$root.userType = $window.userType;
    $scope.$root.userId = $window.userId;

    function getProgramOutline(abbrOrId) {
      return $pertsAjax({'url': '/api/program_outline/' + abbrOrId});
    }

    $scope.breadcrumbs = [];

    if ($routeParams.level && $routeParams.entityId && $routeParams.page) {
        $scope.$root.level = $routeParams.level;
        $scope.$root.entityId = $routeParams.entityId;
        $scope.$root.page = $routeParams.page;
    } else {  // The hash isn't right, or the user has just arrived and has none
        // Signals certain widgets to redirect to more specific realms if they
        // are only showing one thing.
        $scope.$root.redirecting = true;
        $location.path('/programs/all/program_progress');
        return;
    }

    $scope.$root.levelLables = {
        'programs': 'Global level',
        'program': 'Study level',
        'cohort': 'School level',
        'classroom': 'Classroom level'
    };

    $scope.$root.programs = {id: 'all', name: 'Dashboard Home'};
    $scope.$root.educators = {id: 'all', name: 'Educators'};
    $scope.$root.orphans = {id: 'all', name: 'Orphans'};
    $scope.$root.schools = {id: 'all', name: 'Schools'};

    if (arrayContains(['programs', 'educators', 'orphans', 'schools'],
                      $routeParams.level)) {
        // There's no entity to load, just provide a stub that fills in
        // appropriate text to display
        $scope.$root.user = $getStore.get($scope.$root.userId);
        $scope.$root.currentEntity = $scope.$root[$routeParams.level];
    } else {
        // There is an entity providing context for this view; load it and its
        // parents
        $getStore.load([$scope.$root.userId, $scope.$root.entityId]);
        $scope.$root.user = $getStore.get($scope.$root.userId);
        $scope.$root.currentEntity = $getStore.get($scope.$root.entityId);
    }
    var programId, cohortId;
    var contextLoaded;  // a promise to attach breadcrumb definition to
    var programOutlineDeferred = $q.defer();
    $scope.$root.programOutlineLoaded = programOutlineDeferred.promise;
    $scope.$watch('currentEntity', function (value) {
        if (value.name !== undefined) {
            // then the current entity has been loaded, and we can look at it...
            if ($scope.$root.level === 'program') {
                $scope.$root.program = $scope.$root.currentEntity;
                if ($scope.$root.page === 'cohort_progress') {
                    $scope.$root.programList = [$scope.$root.program];
                }
            } else if ($scope.$root.level === 'cohort') {
                $scope.$root.cohort = $scope.$root.currentEntity;
                programId = $scope.$root.cohort.assc_program_list[0];
                contextLoaded = $getStore.load([programId]);
                $scope.$root.program = $getStore.get(programId);
            } else if ($scope.$root.level === 'classroom') {
                $scope.$root.classroom = $scope.$root.currentEntity;
                programId = $scope.classroom.assc_program_list[0];
                cohortId = $scope.classroom.assc_cohort_list[0];
                contextLoaded = $getStore.load([programId, cohortId]);
                $scope.$root.cohort = $getStore.get(cohortId);
                $scope.$root.program = $getStore.get(programId);
            }
            if ($scope.$root.program) {
                var url = '/api/program_outline/' + $scope.$root.program.id;
                $pertsAjax({'url': url}).then(function (outline) {
                    $scope.$root.programOutline = outline;
                    programOutlineDeferred.resolve(outline);
                });
            } else {
                programOutlineDeferred.resolve();
            }
            if (contextLoaded === undefined) {
                contextLoaded = $emptyPromise();
            }
            contextLoaded.then(function () {
                $scope.generateBreadcrumbs();
            });
        }
    }, true);  // true here means watch object value, not object reference
    // (the entity store is specifically designed NOT to change object
    // references)

    // Configure navigation tabs
    var tabConfig = {
        programs: [
            {id: 'program_progress', name: 'Tracking'}
        ],
        program: [
            {id: 'cohort_progress', name: 'Tracking'},
            {id: 'educators', name: 'All Coordinators'}
        ],
        cohort: [
            {id: 'classroom_progress', name: 'Schedule'},
            {id: 'school_roster', name: 'School Roster'},
            {id: 'school_makeups', name: 'School Make-Ups'},
            {id: 'educators', name: 'School Coordinators'},
            {id: 'detail', name: 'Edit School Details'}
        ],
        classroom: [
            {id: 'classroom_roster', name: 'Classroom Roster'},
            {id: 'classroom_makeups', name: 'Classroom Make-Ups'},
            {id: 'detail', name: 'Edit Classroom Details'}
        ]
    };

    $scope.tabs = tabConfig[$scope.$root.level];
    $scope.tabClass = function (tabId) {
        return tabId === $scope.$root.page ? 'active' : '';
    };

    $scope.generateBreadcrumbs = function () {
        var parents;
        /*jshint ignore:start*/
        switch ($scope.$root.level) {
        case 'schools':   parents = [];  break;
        case 'educators': parents = [];  break;
        case 'programs':  parents = [];  break;
        case 'program':   parents = [];
                          if ($scope.$root.userType === 'god') {
                              parents.unshift('programs');
                          }
                          break;
        case 'cohort':    parents = ['program'];
                          if ($scope.$root.userType === 'god') {
                              parents.unshift('programs');
                          }
                          break;
        case 'classroom': parents = ['program', 'cohort'];
                          if ($scope.$root.userType === 'god') {
                              parents.unshift('programs');
                          }
                          break;
        }
        /*jshint ignore:end*/
        var b = [];
        if (parents === undefined) {
            return {};
        } else if (parents.length > 0) {
            b = forEach(parents, function (lvl) {
                if ($scope.$root[lvl]) {
                    return {
                        link: '/' + lvl +
                            '/' + $scope[lvl].id +
                            '/' + tabConfig[lvl][0].id,
                        name: $scope[lvl].name,
                        type: lvl
                    };
                }
            });
        }
        b.push({name: $scope.$root.currentEntity.name, type: $scope.$root.level});
        $scope.breadcrumbs = b;
    };

    // The detail page changes template based on the level
    $scope.detailTemplateUrl = '/static/dashboard_pages/' + $scope.$root.level + '_detail.html';

    // b/c our current version of angular doesn't support dynamic templates,
    // this is a little hack to change up the template based on the route.
    // @todo: fix this when >= 1.1.2 becomes stable.
    $scope.templateUrl = '/static/dashboard_pages/' + $scope.$root.page + '.html';
}

//  *************************  //
//  ******** WIDGETS ********  //
//  *************************  //

PertsApp.directive('tablePageNav', function () {
    'use strict';
    return {templateUrl: '/static/dashboard_widgets/table_page_nav.html'};
});

PertsApp.directive('programProgressList', function () {
    'use strict';
    return {
        scope: {},
        controller: function ($scope, $getStore, $pertsAjax, $location) {
            // We'll need all the user's programs
            $pertsAjax({url: '/api/get/program'}).then(function (response) {
                $scope.programList = $getStore.setList(response);
                var programIds = forEach($scope.programList, function (program) {
                    return program.id;
                });

                if ($scope.$root.redirecting) {
                    if ($scope.programList.length === 1) {
                        $location.path('/program/' + $scope.programList[0].id +
                                       '/cohort_progress');
                        return;
                    } else {
                        // this is the right place to be; stop redirection
                        $scope.$root.redirecting = false;
                    }
                }

                // ... and all the cohorts associated with those programs.
                $pertsAjax({
                    url: '/api/get/cohort',
                    params: {assc_program_list_json: programIds}
                }).then(function (response) {
                    $scope.cohortList = $getStore.setList(response);
                    // Index the cohorts by program so they can be passed to
                    // the correct child.
                    $scope.cohortIndex = {};
                    forEach($scope.cohortList, function (cohort) {
                        var programId = cohort.assc_program_list[0];
                        initProp($scope.cohortIndex, programId, []);
                        $scope.cohortIndex[programId].push(cohort.id);
                    });
                });
            });
        },
        templateUrl: '/static/dashboard_widgets/program_progress_list.html'
    };
});

PertsApp.directive('programProgress', function () {
    'use strict';
    var scope = {
        programId: '@programId',
        cohortIds: '@cohortIds'
    };
    var controller = function ($scope, $getStore, $pertsAjax, $AggregateCohortRow) {
        $scope.$watch('programId', function (value) {
            $scope.program = $getStore.get(value);
        });
        $scope.$watch('cohortIds', function (cohortIds) {
            if (!cohortIds) {
                return;
            }

            cohortIds = $scope.$eval(cohortIds);
            var cohortList = $getStore.getList(cohortIds);
            var outlineUrl = '/api/program_outline/' + $scope.programId;
            $pertsAjax({url: outlineUrl}).then(function (outline) {
              $scope.rows = $scope.buildRows(cohortList, outline);
            });
        });

        $scope.buildRows = function (cohortList, outline) {
            var rows = [];
            forEach(outline.student, function (module) {
                if (module.type === 'activity') {
                    rows.push($AggregateCohortRow(
                        cohortList, module.activity_ordinal));
                }
            });
            return rows;
        };
        $scope.columns = [
            {name: "School", tooltip: "School name",
             colClass: 'name', sortable: true}, // really a cohort name
            {name: "#", tooltip: "Session number",
             colClass: 'session', sortable: true},
            // <classroom session status>
            {name: "Unschd", tooltip: "Unscheduled: number of classrooms who haven't set a date for their session.",
             colClass: 'unscheduled', sortable: true},
            {name: "Bhnd", tooltip: "Behind: number of classrooms behind schedule.",
             colClass: 'behind', sortable: true},
            {name: "Schd/ Compl", tooltip: "Scheduled/Completed: Number of classrooms on track.",
             colClass: 'scheduled_completed', sortable: true},
            {name: "Total", tooltip: "Total number of classrooms.",
             colClass: 'total', sortable: true},
            // </classroom session status>
            {name: "Incmpl Rosters", tooltip: "Incomplete Rosters: classrooms whose student roster hasn't been verified.",
             colClass: 'incomplete_rosters', sortable: true},
            {name: "Uncert", tooltip: "Uncertified Students: students who signed in but weren't recognized.",
             colClass: 'uncertified', sortable: true},
            // <certified study eligible students>
            {name: "Total", colClass: 'study_eligible', sortable: true,
             tooltip: "All certified, study eligible students."},
            {name: "Cmpl", colClass: 'completed', sortable: true,
             tooltip: "Complete: students who have completed the session, as a percent of study eligible students."},
            {name: "Makeup Inelg", colClass: 'makeup_ineligible', sortable: true,
             tooltip: "Makeup Ineligible: students who may NOT participate in a make up session."},
            {name: "Makeup Elg", colClass: 'makeup_eligible', sortable: true,
             tooltip: "Makeup Eligible: students who MAY participate in a make up session."},
            {name: "Not Coded", colClass: 'uncoded', sortable: true,
             tooltip: "Students who should either 1) complete the session " +
                      "or 2) be given a code explaining why they haven't."}
            // </certified study eligible students>
        ];
    };
    return {
        scope: scope,
        controller: controller,
        templateUrl: '/static/dashboard_widgets/program_progress.html'
    };
});

PertsApp.directive('cohortEntry', function () {
    'use strict';
    return {
        scope: {
            cohortId: '@cohortId'
        },
        controller: function ($scope, $getStore, $window) {
            $scope.$watch('cohortId', function (value) {
                $scope.cohort = $getStore.get(value);
                // @todo: there's a lot of things we could try to load if we
                // wanted, because there's a lot of widgets nested under here.
            });
            $scope.userType = $window.userType;
            $scope.show = function () {
                return $scope.$root.level === 'cohort' ||
                    $scope.$root.level === 'classroom';
            };
        },
        templateUrl: '/static/dashboard_widgets/cohort_entry.html'
    };
});


PertsApp.directive('cohortBasics', function () {
    'use strict';
    return {
        scope: {
            cohortId: '@cohortId'
        },
        controller: function ($scope, $getStore, $pertsAjax, $location) {
            $scope.$watch('cohortId', function (value) {
                $scope.cohort = $getStore.get(value);
            });
            $scope.show = function () {
                return $scope.$root.level === 'program' ||
                    $scope.$root.level === 'cohort' ||
                    $scope.$root.level === 'classroom';
            };
            $scope.deleteCohort = function (cohort) {
                if (confirm("Are you sure you want to delete " + cohort.name + "?")) {
                    var url = '/api/delete/' + cohort.id;
                    $pertsAjax({url: url}).then(function () {
                        $location.path('/');
                    });
                }
            };
        },
        templateUrl: '/static/dashboard_widgets/cohort_basics.html'
    };
});

PertsApp.directive('cohortAdmins', function () {
    'use strict';
    return {
        scope: {
            cohortId: '@cohortId'
        },
        controller: function ($scope, $getStore, $pertsAjax) {
            $scope.$watch('cohortId', function (value) {
                if (value) {
                    $scope.cohort = $getStore.get(value);
                    $scope.getAssociatedUsers();
                }
            });
            $scope.getAssociatedUsers = function () {
                // to display admins, we need to see all associated users
                $pertsAjax({
                    url: '/api/get/user',
                    params: {
                        user_type: 'school_admin',
                        owned_cohort_list: $scope.cohort.id
                    }
                }).then(function (response) {
                    $scope.adminList = forEach(response, function (admin) {
                        return $getStore.set(admin);
                    });
                });
            };
            $scope.noAdmins = function () {
                // to display admins, we need to see all associated users
                if ($scope.adminList) {
                    return $scope.adminList.length === 0;
                }
            };
        },
        templateUrl: '/static/dashboard_widgets/cohort_admins.html'
    };
});

PertsApp.factory('$AggregateCohortRow', function ($getStore, $createSearchData, $getPercentString) {
    'use strict';
    return function (cohortList, activityOrdinal) {
        // Each cohort has aggregation data. But this widget/directive
        // represents one activity ordinal out of a set of cohorts. That
        // means we need to summarize subsets of the available aggregation
        // data.
        var aggregate = function () {
            // This will be the new summary
            var data;
            forEach(cohortList, function (cohort) {
                // Extract data relevant to just one activity ordinal.
                var cData = cohort._aggregation_data[activityOrdinal];
                // If the widget's data is currently blank, initialize it
                // with whatever this current cohort has got. Otherwise,
                // go through it and increment each stat.
                if (data === undefined) {
                    data = angular.copy(cData);
                } else {
                    forEach(cData, function (key1, value1) {
                        if (typeof value1 === 'number') {
                            data[key1] += value1;
                        } else {
                            forEach(value1, function (key2, value2) {
                                data[key1][key2] += value2;
                            });
                        }
                    });
                }
            });
            return data;
        };

        return {
            cohortList: cohortList,

            cohortIds: forEach(cohortList, function (c) { return c.id; }),

            activityOrdinal: activityOrdinal,

            data: aggregate(),

            name: function () { return this.cohortList[0].name; },
            unscheduled: function () { return this.data.unscheduled; },
            behind: function () { return this.data.behind; },
            scheduledCompleted: function () {
                return this.data.scheduled + this.data.completed;
            },
            totalClassrooms: function () {
                return this.data.unscheduled + this.data.behind +
                    this.data.completed + this.data.scheduled;
            },
            incompleteRosters: function () {
                return this.data.incomplete_rosters;
            },
            uncertified: function () {
                return this.data.total_students - this.data.certified_students;
            },
            studyEligible: function () {
                return this.data.certified_study_eligible_dict.n;
            },
            complete: function () {
                return this.data.certified_study_eligible_dict.completed;
            },
            pctComplete: function () {
                return $getPercentString(
                    this.data.certified_study_eligible_dict.completed,
                    this.data.certified_study_eligible_dict.n);
            },
            makeupIneligible: function () {
                return this.data.certified_study_eligible_dict.makeup_ineligible;
            },
            makeupEligible: function () {
                return this.data.certified_study_eligible_dict.makeup_eligible;
            },
            uncoded: function () {
                return this.data.certified_study_eligible_dict.uncoded;
            },

            // Parses user objects into easy-to-search data structures: an object
            // and a string. This takes care of many complicated and dynamic data
            // sources and puts everything of interest in one place.
            toSearchObject: function () {
                // Sum up the stats from each cohort.
                return {
                    name: this.name(),
                    session: activityOrdinal,
                    unscheduled: this.unscheduled(),
                    behind: this.behind(),
                    scheduled_completed: this.scheduledCompleted(),
                    total: this.totalClassrooms(),
                    incomplete_rosters: this.incompleteRosters(),
                    uncertified: this.uncertified(),
                    study_eligible: this.studyEligible(),
                    complete: this.complete() + ' (' + this.pctComplete() + ')',
                    makeup_ineligible: this.makeupIneligible(),
                    makeup_eligible: this.makeupEligible(),
                    uncoded: this.uncoded(),
                };
            },
            createSearchData: $createSearchData
        };
    };
});

// Displays statistics broken down by cohort for all the cohorts in a program.
// Calls aggregateCohortProgress for each item in the list.
PertsApp.directive('cohortProgressList', function () {
    'use strict';
    var controller = function ($scope, $AggregateCohortRow, $getStore, $pertsAjax, $location, $window) {

        PaginatedTableController.call(this, $scope);

        $scope.pageSize = 20;
        $scope.stateAbbreviations = ["AK","AL","AR","AZ","CA","CO","CT","DC","DE","FL","GA","GU","HI","IA","ID", "IL","IN","KS","KY","LA","MA","MD","ME","MH","MI","MN","MO","MS","MT","NC","ND","NE","NH","NJ","NM","NV","NY", "OH","OK","OR","PA","PR","PW","RI","SC","SD","TN","TX","UT","VA","VI","VT","WA","WI","WV","WY"];

        // ICF wants there to be a "Testing State"
        $scope.stateAbbreviations.push("TS");

        // get all the cohorts visible to the user in this program
        $scope.$root.programOutlineLoaded.then(function () {
            return $pertsAjax({
                url: '/api/get/cohort',
                params: {
                    assc_program_list: $scope.$root.currentEntity.id,
                    order: 'name'
                }
            });
        }).then(function (response) {
            $scope.cohortList = $getStore.setList(response);

            // Figure out if we should automatically redirect elsewhere
            // because the user doesn't have any choices at this level.
            if ($scope.$root.redirecting && $scope.$root.level === 'program') {
                if ($scope.cohortList.length === 1) {
                    $location.path('/cohort/' + $scope.cohortList[0].id +
                                   '/classroom_progress');
                    return;
                } else {
                    // this is the right place to be; stop redirection
                    $scope.$root.redirecting = false;
                }
            }

            // If we're not redirecting, use the program outline to figure
            // out how to organize the cohorts' aggregated data by
            // activity.
            var rows = $scope.buildRows($scope.cohortList);
            $scope.initializeTable(rows);
        });

        $scope.buildRows = function (cohortList) {
            var rows = [];
            forEach(cohortList, function (cohort) {
                forEach($scope.$root.programOutline.student, function (module) {
                    if (module.type === 'activity') {
                        rows.push($AggregateCohortRow(
                            [cohort], module.activity_ordinal));
                    }
                });
            });
            return rows;
        };

        var getName = function () {
            return '(' + $scope.schoolState + ') ' + $scope.schoolName;
        };

        $scope.createSchool = function () {
            return $pertsAjax({
                url: '/api/put/school',
                params: {name: getName()}
            });
        };

        $scope.createCohort = function (school) {
            return $pertsAjax({
                url: '/api/put/cohort',
                params: {
                    name: getName(),
                    program: $scope.$root.currentEntity.id,
                    school: school.id
                }
            });
        };

        $scope.addSchool = function () {
            $scope.createSchool()
            .then($scope.createCohort)
            .then(function (cohort) {
                cohort = $getStore.set(cohort);
                // Add the cohort to the table's list and rebuild it so the
                // new cohort is displayed.
                $scope.cohortList.push(cohort);
                var newRows = $scope.buildRows([cohort]);
                $scope.fullList = newRows.concat($scope.fullList);
                forEach(newRows, function (row) {
                    row.createSearchData();
                });
                // Clear the school name input box.
                $scope.schoolName = '';
            });
        };

        $scope.columns = [
            {name: "School", tooltip: "School name",
             colClass: 'name', sortable: true}, // really a cohort name
            {name: "#", tooltip: "Session number",
             colClass: 'session', sortable: true},
            // <classroom session status>
            {name: "Unschd", tooltip: "Unscheduled: number of classrooms who haven't set a date for their session.",
             colClass: 'unscheduled', sortable: true},
            {name: "Bhnd", tooltip: "Behind: number of classrooms behind schedule.",
             colClass: 'behind', sortable: true},
            {name: "Schd/ Compl", tooltip: "Scheduled/Completed: Number of classrooms on track.",
             colClass: 'scheduled_completed', sortable: true},
            {name: "Total", tooltip: "Total number of classrooms.",
             colClass: 'total', sortable: true},
            // </classroom session status>
            {name: "Incmpl Rosters", tooltip: "Incomplete Rosters: classrooms whose student roster hasn't been verified.",
             colClass: 'incomplete_rosters', sortable: true},
            {name: "Uncert", tooltip: "Uncertified Students: students who signed in but weren't recognized.",
             colClass: 'uncertified', sortable: true},
            // <certified study eligible students>
            {name: "Total", colClass: 'study_eligible', sortable: true,
             tooltip: "All certified, study eligible students."},
            {name: "Cmpl", colClass: 'complete', sortable: true,
             tooltip: "Complete: students who have completed the session, as a percent of study eligible students."},
            {name: "Makeup Inelg", colClass: 'makeup_ineligible', sortable: true,
             tooltip: "Makeup Ineligible: students who may NOT participate in a make up session."},
            {name: "Makeup Elg", colClass: 'makeup_eligible', sortable: true,
             tooltip: "Makeup Eligible: students who MAY participate in a make up session."},
            {name: "Not Coded", colClass: 'uncoded', sortable: true,
             tooltip: "Students who should either 1) complete the session " +
                      "or 2) be given a code explaining why they haven't."}
            // </certified study eligible students>
        ];
    };
    return {
        scope: {},
        controller: controller,
        templateUrl: '/static/dashboard_widgets/cohort_progress_list.html'
    };
});

// Displays statistics of *one or more* cohorts, broken down by activity
// ordinal. Used in two dashboard views: program_progress and cohort_progress.
PertsApp.directive('aggregateCohortProgress', function () {
    'use strict';
    return {
        scope: {
            showCohortColumn: '@showCohortColumn',
            cohortIds: '@cohortIds',
            activityOrdinal: '@activityOrdinal',
        },
        controller: function ($scope, $getStore, $getPercentString, $AggregateCohortRow) {
            $scope.data = {all: {}, certified: {}};

            $scope.$watch('cohortIds', function (cohortIds) {
                if (cohortIds) {
                    cohortIds = $scope.$eval(cohortIds);
                    $scope.activityOrdinal = $scope.$eval(
                        $scope.activityOrdinal);
                    $scope.cohortList = $getStore.getList(cohortIds);
                    $scope.row = $AggregateCohortRow(
                        $scope.cohortList, $scope.activityOrdinal);
                }
            });
        },
        templateUrl: '/static/dashboard_widgets/aggregate_cohort_progress.html'
    };
});

PertsApp.directive('classroomEntryList', function () {
    'use strict';
    return {
        scope: {},
        controller: function ($scope, $getStore, $pertsAjax) {
            $scope.rows = [];
            $scope.classroomList = [$getStore.get($scope.$root.entityId)];
            // load all the teachers of these classrooms
            var classroomIds = forEach($scope.classroomList, function (c) {
                return c.id;
            });
            $pertsAjax({
                url: '/api/get/user',
                params: {
                    user_type_json: ['teacher', 'school_admin'],
                    owned_classroom_list_json: classroomIds
                }
            }).then(function (response) {
                $getStore.setList(response);
                forEach($scope.classroomList, function (classroom) {
                    var row = {classroom: classroom.id};
                    forEach(response, function (teacher) {
                        if (arrayContains(teacher.owned_classroom_list, classroom.id)) {
                            row.teacher = teacher.id;
                        }
                    });
                    $scope.rows.push(row);
                });
            });
        },
        templateUrl: '/static/dashboard_widgets/classroom_entry_list.html'
    };
});

PertsApp.directive('classroomEntry', function () {
    'use strict';
    return {
        scope: {
            adminOptions: '@adminOptions',
            classroomId: '@classroomId',
            teacherId: '@teacherId'
        },
        controller: function ($scope, $getStore, $pertsAjax, $forEachAsync, $window) {
            var cachedClassroomName;

            $scope.$watch('classroomId + teacherId + adminOptions',
                          function (value) {
                if ($scope.classroomId === undefined ||
                    $scope.teacherId === undefined) {
                    return;
                }
                $scope.classroom = $getStore.get($scope.classroomId);
                $scope.teacher = $getStore.get($scope.teacherId);

                // if adminOptions is true (which is only the case on the
                // dashboard, not in other places this widget is used, like a
                // teacher panel) then look up who else we might want to assign
                // this classroom to as owner.
                if ($scope.adminOptions === 'true') {
                    // Because of our clever permissions-based filtering, we
                    // can be confident users can't re-assign inappropriately.
                    // We do want to limit to the current cohort so the list
                    // isn't too huge.
                    $pertsAjax({
                        url: '/api/get/user',
                        params: {
                            user_type_json: ['teacher', 'school_admin'],
                            assc_cohort_list: $scope.$root.cohort.id
                        }
                    }).then(function (data) {
                        $scope.otherAdmins = forEach(data, function (admin) {
                            // filter out the current teacher
                            if (admin.id !== $scope.teacher.id) {
                                return admin;
                            }
                        });
                    });
                }
            });
            $scope.$watch('classroom.name', function (name) {
                if (!name) {
                    return;
                } else if (!cachedClassroomName) {
                    cachedClassroomName = name;
                    return;
                }
            });
            $scope.deleteClassroom = function () {
                if (confirm("Are you sure you want to delete " + $scope.classroom.name + "?")) {
                    var url = '/api/delete/' + $scope.classroom.id;
                    $pertsAjax({url: url}).then(function () {
                        $window.location.reload();
                    });
                }
            };
            $scope.reassignClassroom = function () {
                // Someone with sufficient permission wants to change the owner
                // of this classroom. That means we need to:
                // * Break relationships
                //   - from old owner to classroom
                //   - from classroom to old owner
                // * Create relationships
                //   - from new owner to classroom
                //   - from classroom to new owner

                $pertsAjax({
                    url: '/api/disown/user/' + $scope.teacher.id +
                         '/classroom/' + $scope.classroom.id
                });

                $pertsAjax({
                    url: '/api/set_owner/user/' + $scope.newOwner.id +
                         '/classroom/' + $scope.classroom.id
                });

                // Chain these two so that the second doesn't take effect
                // before the first. Otherwise the unassociate call may be
                // overridden by the associate call, resulting in a double
                // association.
                $pertsAjax({
                    url: '/api/unassociate/classroom/' + $scope.classroom.id +
                         '/user/' + $scope.teacher.id
                }).then(function () {
                    $pertsAjax({
                        url: '/api/associate/classroom/' + $scope.classroom.id +
                             '/user/' + $scope.newOwner.id
                    }).then(function () {
                        $window.location.reload();
                    });
                });
            };
        },
        templateUrl: '/static/dashboard_widgets/classroom_entry.html'
    };
});

// A collection of methods that various parts of the code need to extract data
// from user entities. Used in UI for direct display, and in search.
PertsApp.factory('$ActivityUIMixin', function ($mixer, $createSearchData, $getPercentString) {
    'use strict';
    return $mixer({
        rosterCompleteLabel: function () {
            return this.roster_complete ? "Yes" : "No";
        },

        scheduledDate: function () {
            if (this.scheduled_date) {
                return datepickr.formatDate(
                    Date.createFromString(this.scheduled_date, 'local'),
                    'n/j/y'
                );
            } else {
                return '';
            }
        },

        interpretedStatus: function (forcedStatus) {
            // @todo:
            // If multi-day activity, interpreted status = status
            var today = new Date();
            var scheduled_date;
            if (this.scheduled_date) {
                scheduled_date = Date.createFromString(
                    this.scheduled_date, 'local');
            } else {
                scheduled_date = false;
            }
            // Default to the activity's status, unless it was overwritten by
            // the optional forcedStatus argument.
            var status = forcedStatus ? forcedStatus : this.status;
            if (status === 'completed' || status === 'aborted') {
                return this.status;
            } else if (!scheduled_date) {
                return 'unscheduled';
            } else if (Date.dayDifference(today, scheduled_date) > 3) {
                return 'behind';
            } else {
                return 'scheduled';
            }
        },

        twelveHourTime: function () {
            // We have to put a layer between the scheduled time on the
            // activity and the text box in the UI for various reasons.
            var s = this.scheduled_time;
            return s ? toTwelveHour(s) : s;
        },

        data: function () { return this._aggregation_data; },

        seData: function () { return this._aggregation_data.certified_study_eligible_dict; },

        uncertified: function () {
            return this.data().total_students - this.data().certified_students;
        },

        studyIneligible: function () {
            return this.data().certified_students - this.seData().n;
        },

        studyEligible: function () { return this.seData().n; },

        // Switches from "completed" to "complete" to avoid confusion
        // in the UI between this statistic and the status of an
        // activity being "completed".
        complete: function () { return this.seData().completed; },

        pctComplete: function () {
            return $getPercentString(this.seData().completed, this.seData().n);
        },

        makeupIneligible: function () { return this.seData().makeup_ineligible; },

        makeupEligible: function () { return this.seData().makeup_eligible; },

        uncoded: function () { return this.seData().uncoded; },

        // Parses user objects into easy-to-search data structures: an object
        // and a string. This takes care of many complicated and dynamic data
        // sources and puts everything of interest in one place.
        toSearchObject: function () {
            return {
                name: this.parent_name,
                roster: this.rosterCompleteLabel(),
                session: this.activity_ordinal,
                // Format the date the same way the datepickr widget does,
                // which requires converting the UTC ISO date string we've
                // got into a javascript date object first.
                date: this.scheduledDate(),
                time: this.twelveHourTime(),
                status: this.interpretedStatus(),
                uncertified: this.uncertified(),
                study_ineligible: this.studyIneligible(),
                study_eligible: this.studyEligible(),
                complete: this.complete() + '(' + this.pctComplete() + ')',
                makeup_ineligible: this.makeupIneligible(),
                makeup_eligible: this.makeupEligible(),
                uncoded: this.uncoded(),
                notes: (this.notes || '').replace('\n', '')
            };
        },
        createSearchData: $createSearchData
    });
});

// Displays statistics broken down by classroom for all the classrooms in a
// cohort. Calls classroomProgress for each item in the list.
PertsApp.directive('classroomProgressList', function () {
    'use strict';
    return {
        scope: {},
        controller: function ($scope, $ActivityUIMixin, $q, $seeStore, $getStore, $pertsAjax, $forEachAsync, $modal, $window) {

            // Insert standard table functionality: selecting, paginating, etc.
            PaginatedTableController.call(this, $scope);
            // We'll want custom selection behavior.
            $scope.turnOffSelection();

            $scope.rightMode = 'stats';  // can also be 'notes'
            $scope.pageSize = 20;  // overrides default of 50

            // If redirection gets this deep, it should stop.
            $scope.$root.redirecting = false;
            $scope.classroomParams = {};
            $scope.availableCohorts = [];

            $scope.columns = [
                {name: "", colClass: "select", sortable: false,
                 tooltip: ""},
                {name: "Class Name", colClass: "name", sortable: true,
                 tooltip: ""},
                {name: "Roster Done?", colClass: "roster", sortable: true,
                 tooltip: "Has the roster been marked as completed on the classroom roster tab?"},
                {name: "#", colClass: "session", sortable: true,
                 tooltip: "Session Number"},
                {name: "Date & Time", colClass: "date", sortable: true,
                 tooltip: "When the session is scheduled to be done."},
                {name: "Status", colClass: "status", sortable: true,
                 tooltip: ""},
                {name: "Uncert", colClass: 'uncertified', sortable: true,
                 tooltip: "Uncertified Students: students who signed in but weren't recognized."},
                {name: "Study Inelg", colClass: 'study_ineligible', sortable: true,
                 tooltip: "Study Ineligible: students with a participation code that makes " +
                          "them ineligible for the study."},
                {name: "Total", colClass: 'study_eligible', sortable: true,
                 tooltip: "All certified, study eligible students."},
                {name: "Cmpl", colClass: 'complete', sortable: true,
                 tooltip: "Complete: students who have completed the session, as a percent of study eligible students."},
                {name: "Makeup Inelg", colClass: 'makeup_ineligible', sortable: true,
                 tooltip: "Makeup Ineligible: students who may NOT participate in a make up session."},
                {name: "Makeup Elg", colClass: 'makeup_eligible', sortable: true,
                 tooltip: "Makeup Eligible: students who MAY participate in a make up session."},
                {name: "Not Coded", colClass: 'uncoded', sortable: true,
                 tooltip: "Students who should either 1) complete the session " +
                          "or 2) be given a code explaining why they haven't."}
            ];

            // pre-load all the activities from this cohort
            $pertsAjax({
                url: '/api/get_schedule',
                params: {
                    assc_cohort_list: $scope.$root.currentEntity.id
                }
            }).then(function (response) {
                var mixedActivities = $ActivityUIMixin.mixList(response);
                var storedActivities = $getStore.setList(mixedActivities);
                storedActivities = $scope.defaultSort(storedActivities);
                $scope.initializeTable(storedActivities);
            });

            $scope.populateMoveMenu = function () {
                // See the other cohorts in this program we can move classrooms and
                // students into; it will be used to populate the move menu.
                var params = {assc_program_list: $scope.$root.program.id};
                if ($scope.$root.userType !== 'god') {
                    // For non-gods, see the user's OWNED cohorts in this program.
                    params.id_json = $window.user.owned_cohort_list;
                }
                return $pertsAjax({
                    url: '/api/see/cohort',
                    params: params
                }).then(function (response) {
                    // Remove *this* cohort from the list b/c it doesn't
                    // make sense to move from and to the same place.
                    var cList = forEach(response, function (c) {
                        if (c.id !== $scope.$root.currentEntity.id) { return c; }
                    });
                    $scope.availableCohorts = $seeStore.setList(cList);
                });
            };

            // Detect users clicking on the "move classroom to cohort" menu,
            // confirm their choice, and launch the moving function.
            $scope.$watch('moveToCohort', function (cohort) {
                if (!cohort) { return; }
                var msg = "Are you sure you want to move " +
                          $scope.selectedList.length + " classrooms to " +
                          cohort.name + "?" +
                          "\n\n" +
                          "This process will take about a minute. It is " +
                          "important not to leave the page before it is " +
                          "complete.";
                if (confirm(msg)) {
                    $scope.moveClassrooms($scope.selectedList, cohort);
                } else {
                    $scope.moveToCohort = undefined;
                }
            });

            $scope.toggleRightMode = function () {
                if ($scope.rightMode === 'stats') {
                    $scope.rightMode = 'notes';
                } else if ($scope.rightMode === 'notes') {
                    $scope.rightMode = 'stats';
                }
            };

            $scope.sessionInstructionsUrl = function () {
                if (!$scope.$root.program || !$scope.$root.program.abbreviation || !$scope.$root.cohort) {
                    return;
                }
                return '/p/' + $scope.$root.program.abbreviation +
                       '/student_orientation?cohort=' + $scope.$root.cohort.id;
            };

            $scope.printSessionInstructions = function () {
                var newWindow = window.open($scope.sessionInstructionsUrl());
                newWindow.print();
            };

            $scope.moveClassrooms = function (classroomIds, newCohort) {
                $scope.showMoveProgressMonitor = true;
                $scope.totalMovedClassrooms = classroomIds.length;
                $scope.totalMovedStudents = 0;
                $scope.numMovedClassrooms = 0;
                $scope.numMovedActivities = 0;
                $scope.numMovedStudents = 0;

                var activityIds = forEach($scope.fullList, function (a) {
                    if (arrayContains(classroomIds, a.assc_classroom_list[0])) {
                        return a.id;
                    }
                });

                // Moving classrooms is so rare, we want to be alerted to it.
                var logMove = function (msg) {
                    $pertsAjax({
                        url: '/api/log/error',
                        params: {
                            message: msg,
                            classrooms: classroomIds,
                            original_cohort: $scope.$root.cohort.id,
                            new_cohort: newCohort.id
                        }
                    });
                };

                logMove("This isn't necessarily an error; it's a hack to " +
                        "notify ourselves about a potentially sensitive " +
                        "operation: a user attempting to move classroom(s). " +
                        "Check for a follow-up message on the result.");

                var moveSingleStudent = function (student) {
                    // It is important to unassociate the student from the
                    // cohort FIRST (before associating them to the new one),
                    // because it also (like associate) cascades the change
                    // through higher entities. Doing it second would erase any
                    // higher associations that overlap with the new
                    // association, like the program.

                    // tl;dr: if you don't do it this way, you get a student
                    // who has no program.

                    return $pertsAjax({
                        url: '/api/unassociate/user/' + student.id +
                             '/cohort/' + $scope.$root.cohort.id
                    }).then(function (response) {
                        return $pertsAjax({
                            url: '/api/associate/user/' + student.id +
                                 '/cohort/' + newCohort.id
                        }).then(function () {
                            $scope.numMovedStudents += 1;
                        });
                    });
                };

                // Get all the students in all these classroom, then
                // reassociate each of them.
                var moveStudentsPromise = $pertsAjax({
                    url: '/api/see/user',
                    params: {assc_classroom_list_json: classroomIds}
                }).then(function (students) {
                    $scope.totalMovedStudents = students.length;
                    return $forEachAsync(students, moveSingleStudent, 'serial');
                });

                // Also reassociate the classrooms themselves.
                var moveSingleClassroom = function (classroomId) {
                    // It is important to unassociate the classroom from the
                    // cohort FIRST (before associating them to the new one),
                    // because it also (like associate) cascades the change
                    // through higher entities. Doing it second would erase any
                    // higher associations that overlap with the new
                    // association, like the program.

                    // tl;dr: if you don't do it this way, you get a classroom
                    // which has no program.

                    return $pertsAjax({
                        url: '/api/unassociate/classroom/' + classroomId +
                             '/cohort/' + $scope.$root.cohort.id
                    }).then(function (response) {
                        return $pertsAjax({
                            url: '/api/associate/classroom/' + classroomId +
                                 '/cohort/' + newCohort.id
                        }).then(function (movedClassroom) {
                            // Update the store with the new relationships.
                            $getStore.set(movedClassroom);
                            $scope.numMovedClassrooms += 1;
                        });
                    });
                };

                // Also reassociate the activities.
                var moveSingleActivity = function (activityId) {
                    return $pertsAjax({
                        url: '/api/unassociate/activity/' + activityId +
                             '/cohort/' + $scope.$root.cohort.id
                    }).then(function (response) {
                        return $pertsAjax({
                            url: '/api/associate/activity/' + activityId +
                                 '/cohort/' + newCohort.id
                        }).then(function () {
                            $scope.numMovedActivities += 1;
                        });
                    });
                };

                var moveClassroomsPromise = $forEachAsync(
                    classroomIds, moveSingleClassroom, 'serial');
                var moveActivitiesPromise = $forEachAsync(
                    activityIds, moveSingleActivity, 'serial');

                // If anything goes wrong with the whole move, the
                // errorCallback() will trigger.
                $q.all([moveStudentsPromise, moveClassroomsPromise]).then(
                    function successCallback() {
                        $scope.showMoveProgressMonitor = false;

                        $scope.selectedList = [];
                        // remove those classrooms' activities from the list
                        $scope.fullList = forEach($scope.fullList, function (a) {
                            if (!arrayContains(classroomIds, a.assc_classroom_list[0])) {
                                return a;
                            }
                        });

                        logMove('classroom(s) were successfully moved');
                    },
                    function errorCallback() {
                        $scope.displayMoveError = true;
                        logMove('classroom(s) were NOT successfully moved');
                    }
                );
            };

            // Sort the activities primarily by classroom, secondarily
            // by ordinal.
            $scope.defaultSort = function (activityList) {
                var compare = function (a, b) {
                    if (a > b) { return +1; }
                    if (a < b) { return -1; }
                    return 0;
                };
                activityList.sort(function (a, b) {
                    return compare(a.parent_name, b.parent_name) ||
                           compare(a.activity_ordinal, b.activity_ordinal);
                });
                return activityList;
            };

            $scope.constructNewClassroomName = function () {
                var p = $scope.classroomParams;
                if (arrayContains([p.name, p.teacher_first_name,
                                   p.teacher_last_name], undefined)) {
                    return '';
                }
                var firstInitial = p.teacher_first_name.substr(0, 1);
                var paren = p.name_extra ? ' (' + p.name_extra + ')' : '';

                return p.teacher_last_name + ' ' + firstInitial + '. - ' +
                       p.name + paren;
            };

            $scope.addClassroom = function (classroomParams) {
                // takes a javascript object,
                // {name: 'English 101', teacher: userObject}
                $scope.showAddForm = false;  // close the form
                $pertsAjax({
                    url: '/api/put/classroom',
                    params: {
                        program: $scope.$root.program.id,
                        cohort: $scope.$root.cohort.id,
                        name: $scope.constructNewClassroomName(),
                        user: $window.userId,
                        teacher_name: classroomParams.teacher_first_name + ' ' + classroomParams.teacher_last_name,
                        teacher_email: classroomParams.teacher_email || '',
                        course_id: classroomParams.course_id
                    }
                }).then(function (classroom) {
                    classroom = $getStore.set(classroom);
                    // When getting activities via /api/get_schedule, the
                    // classroom name comes as part of the activity. We'll have
                    // to assign it manually here.
                    forEach(classroom._student_activity_list, function (a) {
                        a.parent_name = classroom.name;
                    });
                    var mixedList = $ActivityUIMixin.mixList(classroom._student_activity_list);
                    var storedList = $getStore.setList(mixedList);
                    // add it to the user list to it gets a row widget
                    $scope.fullList = storedList.concat($scope.fullList);
                    forEach(storedList, function (a) {
                        a.createSearchData();
                    });
                });
            };

            $scope.confirmDeleteClassrooms = function () {
                // Make sure they didn't click by mistake.
                var msg = "Are you sure you want to delete " +
                    $scope.selectedList.length + " classrooms?";
                if (!confirm(msg)) { return; }

                // First check to see if there are any students in these
                // classrooms. Only allow empty classrooms to be deleted.
                $pertsAjax({
                    url: '/api/get/user',
                    params: {
                        user_type: 'student',
                        assc_classroom_list_json: $scope.selectedList
                    }
                }).then(function (students) {
                    if (students.length > 0) {
                        alert("There are still students in some of these " +
                              "classrooms. You may only delete empty " +
                              "classrooms.");
                    } else {
                        $scope.deleteSelectedClassrooms();
                    }
                });
            };

            $scope.deleteSelectedClassrooms = function (classroomId) {
                // Delete each classroom one by one.
                $forEachAsync($scope.selectedList, function (classroomId) {
                    return $pertsAjax({url: '/api/delete/' + classroomId});
                }, 'serial').then(function () {
                    // Rebuild the list of displayed activities based on which
                    // ones didn't just have their classrooms deleted.
                    $scope.fullList = forEach($scope.fullList, function (a) {
                        if (!arrayContains($scope.selectedList, a.assc_classroom_list[0])) {
                            return a;
                        }
                    });
                    // Uncheck all the select boxes.
                    $scope.selectedList = [];
                });
            };

            var getClassrooms = function () {
                return $pertsAjax({
                    url: '/api/get/classroom',
                    params: {
                        assc_cohort_list: $scope.$root.currentEntity.id
                    }
                }).then(function (classrooms) {
                    $scope.classroomList = $getStore.setList(classrooms);
                });
            };

            var buildDialog = function () {
                var testingDialogMarkup = '' +
                    '<div class="modal-header">' +
                        '<h3>Email Addresses: paste into "To:" field</h3>' +
                    '</div>' +
                    '<div class="modal-body">' +
                        '<p>' +
                            arrayUnique(forEach($scope.classroomList, function (c) {
                                if (arrayContains($scope.selectedList, c.id)) {
                                    return c.teacher_email;
                                }
                            })).join(', ') +
                        '</p>' +
                    '</div>' +
                    '<div class="modal-footer">' +
                        '<button ng-click="close()" class="btn">' +
                            'Close' +
                        '</button>' +
                    '</div>';
                // See angular-ui docs for details on available options.
                // http://angular-ui.github.io/bootstrap/#/modal
                var modalInstance = $modal.open({
                    backdrop: true,
                    keyboard: true,
                    backdropClick: true,
                    backdropFade: true,
                    template:  testingDialogMarkup,
                    controller: function ($scope, $modalInstance) {
                        $scope.close = function () {
                            $modalInstance.dismiss('close');
                        };
                    }
                });
            };

            // Build a dialog box for displaying email addresses of selected users.
            $scope.openDialog = function () {
                getClassrooms().then(buildDialog);
            };

            // Special selection tracking, because activities are always
            // selected in pairs.
            $scope.trackSelection = function (event, classroomId, isSelected) {
                if (
                    isSelected === true &&
                    !arrayContains($scope.selectedList, classroomId)
                ) {
                    $scope.selectedList.push(classroomId);
                } else if (isSelected === false) {
                    arrayRemove($scope.selectedList, classroomId);
                }

                // Lazy-load the moving menu.
                if (isSelected === true && $scope.availableCohorts.length === 0) {
                    $scope.populateMoveMenu();
                }

                // Broadcast the change down to activity rows again, so sibling
                // activities can stay in sync (b/c they both together
                // represent the selected classroom).
                $scope.$broadcast('/table/selectionChange',
                                  classroomId, isSelected);
            };
            // Listen to rows whose checkboxes change and track them.
            $scope.$on('/row/selectionChange', $scope.trackSelection);
        },
        templateUrl: '/static/dashboard_widgets/classroom_progress_list.html'
    };
});

// Displays statistics for a given activity.
PertsApp.directive('activityProgress', function () {
    'use strict';
    return {
        scope: {
            id: '@activityId',
            showProgress: '@showProgress',
            rightMode: '=',
            filterText: '='
        },
        controller: function ($scope, $getStore, $scheduleRules, $timeout) {

            // Insert standard row functionality.
            TableRowController.call(this, $scope, $getStore);
            // We'll want custom selection behavior.
            $scope.turnOffSelection();

            var module;
            $scope.dateValid = undefined;
            $scope.timeRegex = /^((0?[1-9])|(1[012])):([0-5][0-9]) ([AaPp][Mm])$/;
            $scope.scheduledDateFormat = 'n/j/y';  // in php parlance

            // The appropriate incomplete text label (e.g. "unscheduled")
            // will be updated in a $watch of the activity's scheduled date.
            $scope.statusOptions = [
                {value: 'incomplete', text: ''},
                {value: 'completed', text: 'completed'}
            ];

            $scope.$watch('id + $root.program', function () {
                if (!$scope.id || !$scope.$root.program) { return; }

                $scope.activity = $getStore.get($scope.id);

                // Convenient syntax.
                $scope.classroomId = $scope.activity.assc_classroom_list[0];

                $scope.$root.programOutlineLoaded.then(function () {
                    $scope.processScheduling();

                    $scope.activity._twelve_hour_time = $scope.activity.twelveHourTime();

                    $scope.initializeRow($scope.id);
                });
            }, true);

            // Clean up various "blank" input values so they conform to our
            // ajax conventions. An undefined value occurs when user input is
            // invalid, so we don't change the underlying value. An empty
            // string means the field is empty, but since the Datastore field
            // is a time object, leavning it as an empty string isn't an
            // options, instead we need null, which becomes None on the server.
            // Also, we want the hidden value to be 24-hour so that it's
            // sortable as text, allowing the table rows to be sortable.
            $scope.$watch('activity._twelve_hour_time', function (timeStr) {
                if (!$scope.activity) { return; }

                if (timeStr === undefined) {
                    // do nothing
                } else if (timeStr === '') {
                    $scope.activity.scheduled_time = null;
                } else if (typeof timeStr === 'string') {
                    $scope.activity.scheduled_time = toTwentyFourHour(timeStr);
                }
            });

            // These variables control styling and tooltip text of certain
            // table fields, which change based on various conditions.
            var resetWarnings = function () {
                $scope.certClass = '';
                $scope.unaccountedClass = '';
                $scope.mysteryClass = '';
                $scope.certTooltip = '';
                $scope.unaccountedTooltip = '';
                $scope.mysteryTooltip = '';
            };
            resetWarnings();
            // Monitor activity status and update styling and tooltips.
            $scope.$watch('activity.status', function (status) {
                if (status === 'completed') {
                    if (!$scope.activity.roster_complete) {
                        $scope.certClass = 'warning';
                        $scope.certTooltip = "Roster not complete.";
                    }
                    if ($scope.activity.uncertified() > 0) {
                        $scope.uncertifiedClass = 'warning';
                        $scope.uncertifiedTooltip = "Students have signed in with unexpected names.";
                    }
                    if ($scope.activity.makeupEligible() > 0) {
                        $scope.makeupEligibleClass = 'warning';
                        $scope.makeupEligibleTooltip = "These students should make up the session.";
                    }
                    if ($scope.activity.uncoded() > 0) {
                        $scope.uncodedClass = 'warning';
                        $scope.uncodedTooltip = "Students who haven't finished the session should be given a non-participation code.";
                    }
                } else {
                    resetWarnings();
                }
            });

            // Special listener so that activity rows are always selected in
            // pairs by classroom.
            $scope.$on('/table/selectionChange', function (event, classroomId, isSelected) {
                if ($scope.classroomId === classroomId) {
                    $scope.isSelected = isSelected;
                }
            });

            $scope.$watch('dateValid', function () {
                if ($scope.dateValid === false) {
                    $scope.datepickrTooltip = "This date conflicts with the " +
                        "other session.";
                } else {
                    $scope.datepickrTooltip = "";
                }
            });

            var schedulingProcessed = false;
            $scope.processScheduling = function () {
                if (schedulingProcessed) { return; }
                schedulingProcessed = true;
                // determine which part of the program config is relevant
                var programId = $scope.$root.program.id;
                var userType = $scope.activity.user_type;
                var outline = $scope.$root.programOutline[userType];
                forEach(outline, function (m) {
                    if (m.activity_ordinal === $scope.activity.activity_ordinal && m.type === 'activity') {
                        module = m;
                    }
                });

                // interpret relative open date logic
                if (module.date_open_relative_to) {
                    // watch the referenced activities so we can dynamically
                    // adjust what dates are available
                    $scheduleRules.watch($scope.classroomId, module.date_open_relative_to, function (date) {
                        var interval = module.date_open_relative_interval * Date.intervals.day;
                        // An activity is open if BOTH the relative delay is
                        // satisfied AND the absolute open date has passed. So
                        // a given date is valid if it is later than BOTH of
                        // these.
                        var relativeDateOpen = new Date(date.getTime() + interval);
                        var absoluteDateOpen = Date.createFromString(module.date_open, 'local');
                        var dateOpen = new Date(Math.max(relativeDateOpen, absoluteDateOpen));

                        $scope.datepickr.config.dateOpen = dateOpen.toDateString('local');

                        // the calendar's constraints have changed in response
                        // to others being set; re-draw
                        $scope.dateValid = $scope.datepickr.rebuild();

                    });
                } else {
                    $scope.datepickr.config.dateOpen = module.date_open;
                }


                // interpret relative close date logic
                if (module.date_closed_relative_to) {
                    // watch the referenced activities so we can dynamically
                    // adjust what dates are available
                    $scheduleRules.watch($scope.classroomId, module.date_closed_relative_to, function (date) {
                        var interval = module.date_closed_relative_interval * Date.intervals.day;
                        // The effective closed date is either the relative
                        // close interval or the absolute close date, whichever
                        // is sooner.
                        var relativeDateClosed = new Date(date.getTime() + interval);
                        var absoluteDateClosed = Date.createFromString(module.date_closed, 'local');
                        var dateClosed = new Date(Math.min(relativeDateClosed, absoluteDateClosed));

                        $scope.datepickr.config.dateClosed = dateClosed.toDateString('local');

                        // the calendar's constraints have changed in response
                        // to others being set; re-draw
                        $scope.dateValid = $scope.datepickr.rebuild();
                    });
                } else {
                    $scope.datepickr.config.dateClosed = module.date_closed;
                }

                // the calendar has initial constraints (based purely on page-
                // load information) which it didn't have when it was first
                // instantiated in the link() function; re-draw.
                $scope.dateValid = $scope.datepickr.rebuild();

                // monitor the calendar widget and send its value into the
                // the activity when it changes; the getStore will do the put.
                $scope.$watch('datepickr._currentValue', function () {
                    var date = $scope.datepickr.getValue();
                    if (date) {
                        $scope.activity.scheduled_date = date.toDateString('local');
                    }
                });

                if ($scope.activity.scheduled_date) {
                    // if the activity as loaded is already scheduled, tell the
                    // calendar widget
                    var date = Date.createFromString(
                        $scope.activity.scheduled_date, 'local');
                    $scope.datepickr.setDate(date);
                    // send an initial update to listening widgets that this
                    // activity knows its date; further updates will come
                    // from watching the data model
                    $scope.$emit('activitySchedule/scheduledAs',
                                 $scope.id, $scope.activity.scheduled_date);
                }

            };

            // It's critical that the $watch set here, which will communicate
            // the calendar's value to the $scheduleRules service, only be
            // called AFTER all other widgets have had a chance to set up their
            // watchers with that service. Otherwise, widgets will not render
            // correctly on page load because their watchers will not be called
            // initially. The necessary delay is accomplished with this
            // timeout.
            $timeout(function () {
                // when the activity's date changes
                $scope.$watch('activity.scheduled_date', function (dateString) {
                    if (dateString) {
                        var dateObject = Date.createFromString(dateString, 'local');

                        // update the copy of dates that all widgets can see,
                        // so they can adjust their dynamic constraints
                        $scheduleRules.addDate($scope.activity, dateObject);

                        $scope.datepickr.setDate(dateObject);

                        // the user has changed the value of this calendar, it
                        // may have become valid or invalid in response; re-
                        // draw
                        $scope.dateValid = $scope.datepickr.rebuild();

                        // and inform the steps, which are waiting for all
                        // activities to be scheduled before moving on
                        $scope.$emit('activitySchedule/scheduled');
                    }

                    // Update the text label of the status dropdown.
                    var statusText = $scope.activity.interpretedStatus(
                        'incomplete');
                    $scope.statusOptions[0].text = statusText;

                    // IE, that saintly savant of browsers, doesn't know how
                    // to update the displayed value of a select if its options
                    // change dynamically. Force it to update its display by
                    // waiting for the angular digest loop to complete and then
                    // writing the text directly to the DOM.
                    $timeout(function () {
                        $('tr[activity-id="' + $scope.id + '"] .status select').each(function (index, selectNode) {
                            selectNode.options[0].text = statusText;
                        }).trigger('change');
                    }, 1);
                }, true);
            }, 1);

            $scope.$watch('isSelected', function (isSelected) {
                if (!$scope.activity) { return; }
                $scope.$emit(
                    '/row/selectionChange',
                    $scope.activity.assc_classroom_list[0],
                    isSelected
                );
            });

            $scope.$on('/table/toggleSelectAll', function (event, checked) {
                $scope.isSelected = checked;
            });
        },
        link: function (scope, element, attrs) {
            // create datepickers
            var node = $('.datepickr', element).get(0);
            // Although it would be nice to rely on Date.toLocaleDateString(),
            // IE likes to use the verbose style, e.g. "Wednesday, July 23rd,
            // 2014", and we need a compact representation.
            // var config = {dateFormat: 'byLocale'};
            // So instead we manually format it in compact US-style as
            // 1-or-2 digit month / 1-or-2 digit day / 2 digit year
            var config = {dateFormat: 'n/j/y'};
            scope.datepickr = new datepickr(node, config);
            element.addClass('activity-progress');
        },
        templateUrl: '/static/dashboard_widgets/activity_progress.html'
    };
});

// // Debugging code for examining how fast a table is rendered.
// var startTime = new Date();
// var debugText = '';
// var intervalHandle = setInterval(function () {
//     var l = $('.dashboard-table tbody').length;
//     debugText += "\nnumber of tbodies: " + l + " at time: " +
//                 ((new Date()) - startTime) / 1000;
//     if (l >= 10) {
//         clearInterval(intervalHandle);
//         console.log(debugText);
//     }
// }, 100);

// Designed to be mixed into a entity.
PertsApp.factory('$createSearchData', function () {
    'use strict';
    // Parses user objects into easy-to-search data structures: an object
    // and a string. This takes care of many complicated and dynamic data
    // sources and puts everything of interest in one place.
    // Note: the keys of the search object must be the same as the classes
    // applied to the column headers in the columns array.
    return function () {
        try {
            // toSearchObject may reference data that isn't ready. Ignore this,
            // assuming that implementations will re-call this when that data
            // IS ready.
            this._searchObject = this.toSearchObject();
            this._searchText = forEach(this._searchObject, function (k, v) {
                return v ? v + '' : '';  // keeps null from becoming 'null' etc
            }).join("\n").toLowerCase();
        } catch (e) {
            // Generally ignore this, but can use this for debugging:
            console.warn("toSearchObject wasn't ready", '' + this, e);
        }
    };
});

// Create a mixer factory that takes an object or list of objects and adds
// the provided collection of properties to them.
PertsApp.factory('$mixer', function () {
    'use strict';
    return function (mixins) {
        return {
            mix: function (entity) {
                forEach(mixins, function (k, v) {
                    entity[k] = v;
                });
                return entity;
            },
            mixList: function (userList) {
                return forEach(userList, this.mix);
            }
        };
    };
});

// A collection of methods that various parts of the code need to extract data
// from user entities. Used in UI for direct display, and in search.
PertsApp.factory('$CoordinatorUIMixin', function ($mixer, $seeStore, $createSearchData, $window) {
    'use strict';
    return $mixer({
        registered: function () {
            return Date.createFromString(this.created, 'UTC')
                .toLocaleDateString();
        },

        ownedSchools: function () {
            var ownedCohorts = $seeStore.getList(this.owned_cohort_list);
            return forEach(ownedCohorts, function (c) {
                return c.name;
            }).join(', ');
        },

        verified: function () {
            return this.user_type === 'teacher' ? "No" : "Yes";
        },

        // Parses user objects into easy-to-search data structures: an object
        // and a string. This takes care of many complicated and dynamic data
        // sources and puts everything of interest in one place.
        toSearchObject: function () {
            return {
                first_name: this.first_name,
                last_name: this.last_name,
                phone: this.phone,
                registered: this.registered(),
                owned_schools: this.ownedSchools(),
                verified: this.verified()
            };
        },
        createSearchData: $createSearchData
    });
});

// A collection of methods that various parts of the code need to extract data
// from user entities. Used in UI for direct display, and in search.
PertsApp.factory('$StudentUIMixin', function ($mixer, $createSearchData, $window) {
    'use strict';
    return $mixer({
        // Translates certified true/false into display text for select.
        // $scope.getCertifiedLabel = function (certified) {
        certifiedLabel: function (certified) {
            if (certified === undefined) { certified = this.certified; }
            return certified ? 'Certified' : 'Uncertified';
        },

        progressLabel: function (activityOrdinal) {
            var p = this._aggregation_data[activityOrdinal].progress;
            return (p || 0) + '%';
        },

        codeLabel: function (activityOrdinal) {
            var code = this['s' + activityOrdinal + '_status_code'];
            return code ? $window.statusCodes[code].label : '';
        },

        // Parses user objects into easy-to-search data structures: an object
        // and a string. This takes care of many complicated and dynamic data
        // sources and puts everything of interest in one place.
        toSearchObject: function () {
            return {
                first_name: this.first_name,
                last_name: this.last_name,
                student_id: this.student_id || '',
                certified: this.certifiedLabel(),
                by: this.uploaded_by_admin ? 'upload' : 'signin',
                code1: this.codeLabel(1),
                code2: this.codeLabel(2),
                progress1: this.progressLabel(1),
                progress2: this.progressLabel(2),
                classroom: this.classroom_name
            };
        },
        createSearchData: $createSearchData
    });
});

PertsApp.controller('RosterTableController', function ($StudentUIMixin, $scope, $timeout, $seeStore, $getStore, $pertsAjax, $location, $forEachAsync, $window) {
    'use strict';

    // Insert standard table functionality: selecting, paginating, etc.
    PaginatedTableController.call(this, $scope);

    // Debugging function for counting the watchers on a page.
    $scope.wcount = function() {
        $timeout(function() {
            $scope.watchers = (function(scope) {
                var watchers = (scope.$$watchers) ? scope.$$watchers.length : 0;
                var child = scope.$$childHead;
                while (child) {
                    watchers += (child.$$watchers) ? child.$$watchers.length : 0;
                    child = child.$$nextSibling;
                }
                return watchers;
            }($scope));
        });
    };

    $scope.printableTable = false;

    $scope.fullList = [];  // all students in the roster
    $scope.destinationClassrooms = [];  // classrooms you could move a user to

    $scope.summaryColumns = [
        {name: "Session", colClass: 'session'},
        {name: "Uncertified", colClass: 'uncertified',
         tooltip: "Students who signed in but weren't recognized."},
        {name: "Certified", colClass: 'certified',
         tooltip: "Students who were entered or approved by an administrator."},
        {name: "Study Ineligible", colClass: 'study_ineligible',
         tooltip: "Students with a non-participation code that makes " +
                  "them ineligible for the study."},
        {name: "Study Eligible", colClass: 'study_eligible',
         tooltip: "Any certified student who is not study ineligible."},
        {name: "Completed", colClass: 'completed',
         tooltip: "Students who have completed the session (100% progress)."},
        {name: "Make-Up Ineligible", colClass: 'makeup_ineligible',
         tooltip: "Students who may NOT participate in a make up session."},
        {name: "Make-Up Eligible", colClass: 'makeup_eligible',
         tooltip: "Students who MAY participate in a make up session."},
        {name: "Uncoded", colClass: 'uncoded',
         tooltip: "Students who should either 1) complete the session " +
                  "or 2) be given a code explaining why they haven't."}
    ];

    $scope.columns = [
        {name: "", colClass: 'select', sortable: false, tooltip: ""},
        {name: "First Name", colClass: 'first_name', sortable: true, tooltip: ""},
        {name: "Last Name", colClass: 'last_name', sortable: true, tooltip: ""},
        {name: "Student ID", colClass: 'student_id', sortable: true, tooltip: ""},
        {name: "Progress", colClass: 'session_progress', sortable: false, tooltip: ""},
        // the css class 'progress' collides with bootstrap
        // {name: "Progress", colClass: 'progress_pd', sortable: false, tooltip: ""},
        {name: "Participation Code", colClass: 'status_code', sortable: false, tooltip: ""}
    ];

    // Columns vary a little according to dashboard level.
    var certifiedColumn = {name: "Certified", colClass: 'certified',
        sortable: true, tooltip: ""};
    var classroomColumn = {name: "Classroom", colClass: 'classroom',
        sortable: true, tooltip: ""};

    var params = {};
    if ($scope.$root.level === 'classroom') {
        // At the classroom level, we can set 'certified' or 'mystery'
        $scope.columns.splice(4, 0, certifiedColumn);
        // and we want only students within the current classroom
        params.assc_classroom_list = $scope.$root.currentEntity.id;
    } else if ($scope.$root.level === 'cohort') {
        // At the cohort level, instead of a certified setter, there's
        // a link to the student's classroom.
        $scope.columns.splice(1, 0, classroomColumn);
        params.assc_cohort_list = $scope.$root.currentEntity.id;
    }

    // Get all the users in this classroom so we can build the roster.
    $pertsAjax({
        url: '/api/get_roster',
        params: params
    }).then(function (response) {
        // Add some methods to each user which teach them out to output their
        // data in more useful ways. Used both in search and for direct
        // display.
        var mixedUsers = $StudentUIMixin.mixList(response);
        // Once we have all the users for this page, save them to the store so
        // their references are optimized. The store ignores methods.
        var storedUsers = $getStore.setList(mixedUsers);
        // Populate the model.
        $scope.initializeTable(storedUsers);
        // The roster is already sorted by last name. But it makes more sense,
        // when viewing it as a school roster, to have it also sorted by
        // classroom.
        if ($scope.$root.level === 'cohort') {
            $scope.sortBy(1);  // classroom name
            $scope.sortedColumn = undefined;  // don't highlight this col
        }

        // HP17 runs B and C have only 1 session
        $scope.setMakeupSession(1);
    });

    // Get all the classrooms from this cohort so we can populate
    // the moving dropdown, but do it lazily once the user has selected a row.
    $scope.loadClassroomNames = function (event, id, isSelected) {
        if (
            $scope.destinationClassrooms.length > 0 ||  // already loaded
            isSelected === undefined  // page just starting up; ignore
        ) { return; }
        var cohort = $scope.$root.cohort;
        $pertsAjax({
            url: '/api/see/classroom',
            params: {
                assc_cohort_list: cohort.id
            }
        }).then(function (response) {
            var cList = $seeStore.setList(response);
            if ($scope.$root.level === 'classroom') {
                // Remove *this* classroom from the list (if this is the
                // classroom level) b/c it doesn't make sense to move from and
                // to the same place.
                $scope.destinationClassrooms = forEach(cList, function (c) {
                    if (c.id !== $scope.classroom.id) { return c; }
                });
            } else {
                // This is the cohort level. No need to remove a classroom
                // from the list of destinations.
                // Also, provide a index of classroom names for display in the
                // school roster.
                $scope.destinationClassrooms = cList;
            }
        });
    };
    $scope.$on('/row/selectionChange', $scope.loadClassroomNames);

    // Watch changes to user properties, and calculate stats on who's
    // certified or not.
    $scope.$watch('fullList', function () {
        if (!$scope.fullList) { return; }
        $scope.summary = {
            1: $scope.summarizeStudents($scope.fullList, 1),
            2: $scope.summarizeStudents($scope.fullList, 2)
        };
    }, true);

    // Change whether you're looking at makeups for session 1 or 2.
    $scope.setMakeupSession = function (s) {
        $scope.searchText = '';
        $scope.makeupSession = s;
        $scope.printableTable = false;
        // One of the things that search does is filter out makeup ineligible
        // students for a specific session. So now that the session is
        // different, re-run search.
        $scope.initializeTable($scope.fullList);
    };

    $scope.additionalSearchRules = function (searchList) {
        if ($scope.makeups) {
            // If the session you want to look at hasn't been set, don't do
            // anything (this is the state of the page when you first arrive).
            if (!$scope.makeupSession) {
                return [];
            }
            var s = $scope.makeupSession;
            // Filter the search results based on whether it's a makeup or not.
            return forEach(searchList, function (user) {
                // To be eligible for a makeup, you must not already be done
                // with the session, and you must not have a code that makes
                // you ineligible.
                var progress = user._aggregation_data[s].progress;
                var code = user['s' + s + '_status_code'];
                var makeupEligible = (!code ||
                    $window.statusCodes[code].makeup_eligible);
                if (progress !== 100 && makeupEligible) {
                    return user;
                }
            });
        } else {
            // Otherwise no need to do extra filtering.
            return searchList;
        }
    }

    // Very similar to the summarize_students method of the
    // Aggregator, but calculates extra stuff desired in the view.
    $scope.summarizeStudents = function (students, activityOrdinal) {
        var sessionSummary = {
            uncertified: 0,
            certified: 0,
            studyIneligible: 0,
            studyEligible: 0,
            completed: 0,
            makeupIneligible: 0,
            makeupEligible: 0,
            uncoded: 0
        };

        forEach(students, function (user) {
            var status1 = $window.statusCodes[user.s1_status_code] || {};
            var status2 = $window.statusCodes[user.s2_status_code] || {};
            if (status1.exclude_from_counts || status2.exclude_from_counts) {
                // These students aren't counted at all.
                return;
            }

            var aggData = user._aggregation_data[activityOrdinal];
            var statusCode = user['s' + activityOrdinal + '_status_code'];
            var status = $window.statusCodes[statusCode] || {};

            if (user.certified) {
                sessionSummary.certified += 1;
            } else {
                sessionSummary.uncertified += 1;
                // Uncertified students aren't counted in any other
                // category.
                return;
            }

            if (statusCode) {
                if (!status.study_eligible) {
                    // Don't count this student in any other categories.
                    // Skip to next one.
                    sessionSummary.studyIneligible += 1;
                    return;
                }

                if (status.counts_as_completed) {
                    sessionSummary.completed += 1;
                } else if (status.makeup_eligible) {
                    sessionSummary.makeupEligible += 1;
                } else {
                    sessionSummary.makeupIneligible += 1;
                }
            } else if (aggData.progress === 100) {
                sessionSummary.completed += 1;
            } else {
                sessionSummary.uncoded += 1;
            }

            sessionSummary.studyEligible += 1;
        });

        return sessionSummary;
    };

    $scope.rosterCompleteDate = function () {
        if (!$scope.classroom || !$scope.classroom.roster_completed_datetime) {
            // Don't freak out if the classroom isn't loaded yet.
            return;
        }
        var dateStr = $scope.classroom.roster_completed_datetime;
        var date = Date.createFromString(dateStr, 'UTC');
        return date.toLocaleDateString();
    };

    $scope.deleteSelectedUsers = function () {
        var deleteUser = function (userId) {
            return $pertsAjax({url: '/api/delete/' + userId});
        };

        var studentIds = $scope.selectedList.slice(0);  // copy array
        // Deselect all users.
        $scope.selectedList = [];

        // Call deleteUser() for each student to be deleted, then
        // update the view.
        $forEachAsync(studentIds, deleteUser, 'serial').then(function () {
            // Remove the deleted users from the table
            $scope.fullList = forEach($scope.fullList, function (u) {
                if (!arrayContains(studentIds, u.id)) {
                    return u;
                }
            });
        });
    };

    $scope.addUser = function (user) {
        // takes a javascript object,
        // e.g. {first_name: 'mister', last_name: 'ed'}
        user.classroom = $scope.$root.classroom.id;
        user.user_type = 'student';
        user.certified = true;
        user.uploaded_by_admin = true;
        return $pertsAjax({
            url: '/api/put/user',
            params: user
        }).then(function (response) {
            // Add it to the get store so the row widget can connect
            // to the data. It's important to do this before adding it to
            // the scope b/c part of what getStore does is manage
            // references. The *result* of getStore.set() has its
            // references set correctly, while reponse does not.
            var mixedUser = $StudentUIMixin.mix(response);
            var storedUser = $getStore.set(mixedUser);
            // add it to the user list to it gets a row widget
            // N.B. Don't use push or unshift b/c that won't change the
            // reference in fullList and thus won't trigger a watcher to update
            // the UI. Assignment does change the reference.
            $scope.fullList = [storedUser].concat($scope.fullList);
            storedUser.createSearchData();

        });
    };

    $scope.addSingleUser = function () {
        $scope.addUser($scope.newStudent).then(function () {
            // clear the text fields
            $scope.newStudent = {};
            // show visual confirmation
            $('#confirm_add_single_user').show().fadeOut(4000);
        });
    };

    $scope.addCsvUsers = function () {
        $scope.alert = false;
        $scope.addCsvUsersBusy = true;

        var sep = "\t";  // csv separator
        var requiredColumns = [
            "first_name",
            "last_name",
            "student_id",
            "s1_status_code",
            "s2_status_code",
            "consent"
        ];
        var rows = $scope.userCsv.split("\n");

        // remove the first row; make sure columns are right
        var providedColumns = rows.splice(0, 1)[0].split(sep);
        if (!arrayEqual(providedColumns, requiredColumns)) {
            $scope.alert = {
                type: 'error',
                msg: "Invalid headers. Must be tab-separated with " +
                    "columns " + requiredColumns.join("\t")
            };
        }

        // build a list of user objects
        var userList = forEach(rows, function (row) {
            if (row === '') { return; }  // skip blank lines
            var fields = row.split(sep);
            if (fields.length !== requiredColumns.length) {
                $scope.alert = {
                    type: 'error',
                    msg: "Invalid data. This row doesn't have " +
                        "the right number of fields: " + row
                };
            }
            var user = {};
            forEach(requiredColumns, function (col, index) {
                user[col] = fields[index];
            });
            return user;
        });

        if (!$scope.alert) {
            // Adding many users at once can take a long time if done one
            // by one, so POST the whole batch.
            $pertsAjax({
                url: '/api/batch_put_user',
                method: 'POST',
                params: {
                    user_names: userList,
                    classroom: $scope.$root.classroom.id,
                    user_type: 'student',
                    certified: true,
                    uploaded_by_admin: true
                }
            }).then(function (response) {
                // Add new users to the get store so the row widget can
                // connect to the data. It's important to do this before
                // adding it to the scope b/c part of what getStore does
                // is manage references. The *result* of getStore.set()
                // has its references set correctly, while reponse does
                // not.
                var mixedList = $StudentUIMixin.mixList(response);
                var storedList = $getStore.setList(mixedList);
                // add it to the user list to it gets a row widget
                $scope.fullList = storedList.concat($scope.fullList);
                forEach(storedList, function (e) {
                    e.createSearchData();
                });
                // clear the text fields
                $scope.userCsv = '';
                // Trigger a change event on the textarea so that the
                // autogrow plugin can do its work.
                setTimeout(function () {
                    $('form[name="addCsvUsersForm"] textarea').trigger('change');
                }, 1);
                // show visual confirmation
                $scope.addCsvUsersBusy = false;
                $('#confirm_add_csv_users').show().fadeOut(4000);
            });
        } else {
            $scope.addCsvUsersBusy = false;
        }
    };

    $scope.markRosterAsComplete = function () {
        // Most of these objects are linked through the getStore, so just
        // changing their properies is sufficient to save to the server.
        forEach($scope.fullList, function (user) {
            user.certified = true;
        });
        $scope.classroom.roster_complete = true;
        var nowDateStr = (new Date()).toDateTimeString('UTC');
        $scope.classroom.roster_completed_datetime = nowDateStr;

        // But we need to redundantly store the roster completion on
        // related activity entities as well, and since they're not loaded
        // yet, that's more work. First look them up, then sent an update
        // request to each.
        $pertsAjax({
            url: '/api/see/activity',
            params: {
                // Must specify a see property b/c activities don't have
                // names, and name is the default. W/o specifying this,
                // you would get no results.
                see: 'id',
                assc_classroom_list: $scope.classroom.id
            }
        }).then(function (response) {
            forEach(response, function (activity) {
                $pertsAjax({
                    url: '/api/put/activity/' + activity.id,
                    params: {roster_complete: true}
                });
            });
        });
    };

    // Detect users clicking on the "move student to classroom" menu,
    // confirm their choice, and launch the moving function.
    $scope.$watch('moveToClassroom', function (classroom) {
        if (!classroom) { return; }
        var msg = "Are you sure you want to move " +
                  $scope.selectedList.length + " students to " +
                  classroom.name + "?";
        if (confirm(msg)) {
            $scope.moveStudents($scope.selectedList, classroom);
        } else {
            $scope.moveToClassroom = undefined;
        }
    });

    // Re-associate students to another classroom.
    $scope.moveStudents = function (studentIds, newClassroom) {
        var moveSingleStudent = function (student_id) {
            // It is important to unassociate the student from the
            // classroom FIRST (before associating them to the new
            // one), because it also (like associate) cascades the
            // change through higher entities. Doing it second would
            // erase any higher associations that overlap with the new
            // association, like the cohort and program.

            // tl;dr: if you don't do it this way, you get a student
            // who has no program or cohort.

            return $pertsAjax({
                url: '/api/unassociate/user/' + student_id +
                     '/classroom/' + $scope.classroom.id
            }).then(function (response) {
                return $pertsAjax({
                    url: '/api/associate/user/' + student_id +
                         '/classroom/' + newClassroom.id
                });
            });
        };

        $forEachAsync(studentIds, moveSingleStudent, 'serial').then(function () {
            $scope.selectedList = [];
            // remove those users from the list
            $scope.fullList = forEach($scope.fullList, function (u) {
                if (!arrayContains(studentIds, u.id)) {
                    return u;
                }
            });
        });
    };

    $scope.togglePrintableTable = function () {
        $scope.searchText = '';
        $scope.printableTable = !$scope.printableTable;
        if ($scope.printableTable) {
            setTimeout($window.print, 100);
        }
    };
});

PertsApp.directive('printableTable', function () {
    return {
        templateUrl: '/static/dashboard_widgets/printable_table.html'
    };
});

PertsApp.controller('RosterRowController', function ($timeout, $scope, $getStore, $seeStore, $pertsAjax, $location, $modal, $emptyPromise, $window) {
    'use strict';

    // Insert standard table row functionality: selecting, searching
    TableRowController.call(this, $scope, $getStore);

    $scope.mergeTargets = {};

    // Boot up the widget when the user's id is available.
    $scope.$watch('id', function (id) {
        $scope.user = $scope.initializeRow(id);
    });

    // Read sessions from server's program config and determine the
    // number of session rows the student needs.
    $scope.$root.programOutlineLoaded.then(function (outline) {
        $scope.sessions = forEach(outline.student, function (module) {
            if (module.type === 'activity') {
                return module;
            }
        });
    });

    // Prompt user to choose a merge id if they choose the merge code.
    $scope.$watch('user.s1_status_code', function (newCode, oldCode) {
        // Don't open dialogs if the code hasn't *really* changed (the
        // watch function always fires once as the page loads).
        if (newCode === 'MWN' && oldCode !== 'MWN') {
            $scope.openDialog(1);
        }

        $scope.hasMWN = $scope.user.s1_status_code === 'MWN' ||
            $scope.user.s2_status_code === 'MWN';

        // Clear user merge ids if they don't apply. Javascript null is
        // eventually translated to python None on the server.
        if ($scope.user.s1_merge_id && $scope.user.s1_status_code !== 'MWN') {
            $scope.user.s1_merge_id = null;
        }
    });

    $scope.$watch('user.s2_status_code', function (newCode, oldCode) {
        if (newCode === 'MWN' && oldCode !== 'MWN') {
            $scope.openDialog(2);
        }

        $scope.hasMWN = $scope.user.s1_status_code === 'MWN' ||
            $scope.user.s2_status_code === 'MWN';

        if ($scope.user.s2_merge_id && $scope.user.s2_status_code !== 'MWN') {
            $scope.user.s2_merge_id = null;
        }
    });

    $scope.$watch('user.s1_merge_id', function (id) {
        if (!id) { return; }
        $scope.mergeTargets[1] = $getStore.get(id);
    });

    $scope.$watch('user.s2_merge_id', function (id) {
        if (!id) { return; }
        $scope.mergeTargets[2] = $getStore.get(id);
    });

    // Wrangle status codes into a nice format for drop-down menus.
    $scope.statusCodes = forEach($window.statusCodes, function (code, info) {
        var group;
        if (info.study_eligible) {
            if (info.makeup_eligible) {
                group = "Make-Up Eligible";
            } else {
                group = "Make-Up Ineligible";
            }
        } else {
            group = "Study Ineligible";
        }
        return {
            id: code,
            label: info.label,
            group: group
        };
    });

    // Add a blank option so the drop down menu can be cleared.
    // Javascript null will translate to python None.
    $scope.statusCodes.unshift({id: null, label: ''});

    $scope.openDialog = function (activityOrdinal) {
        var parentScope = $scope;
        var controller = function ($scope, $modalInstance) {
            $scope.close = function () {
                $modalInstance.dismiss('close');
            };
        };
        var dialogMarkup = '' +
            '<div class="modal-header">' +
                '<h3>Merge With</h3>' +
            '</div>' +
            '<div class="modal-body">' +
                '<p>' +
                    'Merge student <strong>' + $scope.user.first_name +
                    ' ' + $scope.user.last_name + '</strong> with:' +
                '</p>' +
                '<p>' +
                    '<select chosen-select ' +
                            'data-placeholder="merge with student..." ' +
                            'select-options="mergeList" ' +
                            'ng-options="u.id as u.label group by u.group for u in mergeList" ' +
                            'ng-model="user.s' + activityOrdinal + '_merge_id">' +
                    '</select>' +
                '</p>' +
            '</div>' +
            '<div class="modal-footer">' +
                '<button ng-click="close()" class="btn btn-primary">' +
                    'Close' +
                '</button>' +
            '</div>';

        // To display this dialog correctly, we need a list of all the
        // students in the cohort. Only load this when the dialog is
        // first opened b/c most of the time we won't need it.
        if ($scope.mergeList) {
            var promise = $emptyPromise();
        } else {
            var promise = $pertsAjax({
                url: '/api/get_roster',
                params: { assc_cohort_list: $scope.$root.cohort.id }
            }).then(function (userList) {
                // Take the user represented by this row out of the
                // list, because it doesn't make any sense to merge
                // a student with themselves.
                userList = userList.filter(function (user) {
                    return user.id !== $scope.user.id;
                })
                $scope.mergeList = forEach(userList, function (u) {
                    return {
                        id: u.id,
                        label: u.first_name + ' ' + u.last_name,
                        group: u.classroom_name
                    };
                });
            });
        }
        promise.then(function () {
            var modalInstance = $modal.open({
                backdrop: true,
                keyboard: true,
                backdropFade: true,
                scope: $scope,
                template:  dialogMarkup,
                controller: controller
            });
        });
    };
});

PertsApp.directive('schoolRosterTable', function () {
    return {
        scope: {
            classroom: '=classroom',
            cohort: '=cohort'
        },
        controller: 'RosterTableController',
        // link: function (scope, element, attrs) {
        //     // running sortBy sets scope.reverseSort and scope.sortedColumn
        //     var table = element.children('table.roster_table').get();
        //     scope.sortBy = sortByFactory(scope, table, 'tbody');
        // },
        templateUrl: '/static/dashboard_widgets/school_roster_table.html'
    };
});

PertsApp.directive('schoolRosterRow', function () {
    return {
        scope: {
            id: '@userId',
            // filterText: '=filterText',
            classroom: '=classroom',
            isPinned: '=isPinned'
        },
        controller: 'RosterRowController',
        templateUrl: '/static/dashboard_widgets/school_roster_row.html'
    };
});

PertsApp.directive('classroomRosterTable', function () {
    return {
        scope: {
            classroom: '=classroom',
            cohort: '=cohort'
        },
        controller: 'RosterTableController',
        templateUrl: '/static/dashboard_widgets/classroom_roster_table.html'
    };
});

PertsApp.directive('classroomRosterRow', function () {
    return {
        scope: {
            id: '@userId',
            filterText: '=filterText',
            classroom: '=classroom'
        },
        controller: 'RosterRowController',
        templateUrl: '/static/dashboard_widgets/classroom_roster_row.html'
    };
});

PertsApp.directive('schoolMakeupsTable', function () {
    return {
        scope: {
            classroom: '=classroom',
            cohort: '=cohort',
            makeups: '=makeups'
        },
        controller: 'RosterTableController',
        templateUrl: '/static/dashboard_widgets/school_makeups_table.html'
    };
});

PertsApp.directive('schoolMakeupsRow', function () {
    return {
        scope: {
            id: '@userId',
            filterText: '=filterText',
            classroom: '=classroom',
            makeupSession: '=makeupSession'
        },
        controller: 'RosterRowController',
        templateUrl: '/static/dashboard_widgets/school_makeups_row.html'
    };
});

PertsApp.directive('classroomMakeupsTable', function () {
    return {
        scope: {
            classroom: '=classroom',
            cohort: '=cohort',
            makeups: '=makeups'
        },
        controller: 'RosterTableController',
        templateUrl: '/static/dashboard_widgets/classroom_makeups_table.html'
    };
});

PertsApp.directive('classroomMakeupsRow', function () {
    return {
        scope: {
            id: '@userId',
            filterText: '=filterText',
            classroom: '=classroom',
            makeupSession: '=makeupSession'
        },
        controller: 'RosterRowController',
        templateUrl: '/static/dashboard_widgets/classroom_makeups_row.html'
    };
});

PertsApp.directive('swappableStatusSelect', ['$compile', function ($compile) {
    var link = function (scope, element, attrs) {
        var hoverTriggered = false;
        var parentRow = element.parents('tr');
        parentRow.hover(function mouseover() {
            if (hoverTriggered) { return; }
            hoverTriggered = true;
            parentRow.unbind('hover');
            var activityOrdinal = scope.$eval(attrs.activityOrdinal);
            var markup =
                '<div>' +
                    '<select styled-select ' +
                            'ng-model="user[\'s' + activityOrdinal + '_status_code\']" ' +
                            'ng-options="o.id as o.label group by o.group for o in statusCodes | orderBy:[\'group\', \'label\']">' +
                    '</select>' +
                '</div>';
            var newElement = $compile(markup)(scope);
            element.hide();
            element.parent().prepend(newElement);
            if (scope.statusSelectSwap) {
                scope.$apply(scope.statusSelectSwap);
            }
        });
    };
    return {
        scope: true,
        link: link
    };
}]);

PertsApp.directive('userBasics', function () {
    'use strict';
    return {
        scope: {
            id: '@userId',
            mode: '@mode'
        },
        controller: function ($scope, $getStore, $pertsAjax, $window) {
            $scope.$watch('id', function (value) {
                $scope.user = $getStore.get(value);
            });
            $scope.syncNames = function () {
                if (!$scope.user.name) {
                    $scope.user.name = $scope.user.first_name;
                }
            };
            $scope.deleteUser = function (user) {
                if (confirm("Are you sure you want to delete " + user.login_email + "?")) {
                    var url = '/api/delete/' + user.id;
                    $pertsAjax({url: url}).then(function () {
                        window.location.reload();
                    });
                }
            };
            $scope.submitAsRegistrationSurvey = function () {
                $scope.user.registration_complete = true;
                $getStore.synchronize().then(function () {
                    $window.location.href = '/p/' + $window.programAbbr + '/teacher_panel';
                });
            };
        },
        templateUrl: '/static/dashboard_widgets/user_basics.html'
    };
});

PertsApp.directive('changePassword', function () {
    'use strict';
    return {
        scope: {
            id: '@userId'
        },
        controller: function ($scope, $getStore, $pertsAjax) {
            $scope.newPasswordBlurred = false;
            $scope.repeatPasswordBlurred = false;
            $scope.success = null;
            $scope.$watch('id', function (value) {
                $scope.user = $getStore.get(value);
            });
            $scope.isMe = function () {
                return window.userId === $scope.id;
            };
            $scope.passwordsMatch = function () {
                if (!$scope.newPassword || !$scope.repeatPassword) {
                    return false;
                } else {
                    return $scope.newPassword === $scope.repeatPassword;
                }
            };
            $scope.changePassword = function () {
                $scope.success = null;
                $pertsAjax({
                    url: '/api/change_password',
                    method: 'POST',
                    params: {
                        username: $scope.user.login_email,
                        current_password: $scope.currentPassword,
                        new_password: $scope.newPassword
                    }
                }).then(function (response) {
                    if (response === 'changed') {
                        $scope.success = true;
                        $scope.successMessage = "Password changed.";
                        $scope.currentPassword = '';
                        $scope.newPassword = '';
                        $scope.repeatPassword = '';
                        $scope.newPasswordBlurred = false;
                        $scope.repeatPasswordBlurred = false;
                    } else if (response === 'invalid_credentials') {
                        $scope.success = false;
                        $scope.successMessage = "Incorrect password. Password has not been changed.";
                    }
                });
            };
        },
        templateUrl: '/static/dashboard_widgets/change_password.html'
    };
});


PertsApp.directive('userEntryList', function () {
    'use strict';
    var controller = function ($scope, $CoordinatorUIMixin, $seeStore, $getStore, $pertsAjax, $forEachAsync, $modal, $window) {

        PaginatedTableController.call(this, $scope);

        $scope.columns = [
            {name: "", colClass: 'select', sortable: false},
            {name: "First", colClass: 'first_name', sortable: true},
            {name: "Last", colClass: 'last_name', sortable: true},
            {name: "Phone #", colClass: 'phone', sortable: true},
            {name: "Date Registered", colClass: 'registered', sortable: true},
            {name: "Oversees Schools", colClass: 'owned_schools', sortable: false},
            {name: "Verified?", colClass: 'verified', sortable: true}
        ];

        var params = {user_type_json: ['school_admin', 'teacher']};
        if ($scope.$root.level === 'program') {
            // filter by given program
            params.assc_program_list = $scope.$root.entityId;
        } else if ($scope.$root.level === 'cohort') {
            // filter by given cohort, but use 'owned' list b/c
            // that's how school admins are related.
            params.owned_cohort_list = $scope.$root.entityId;
        }

        // Query for relevant users.
        $pertsAjax({
            url: '/api/get/user',
            params: params
        }).then(function (response) {
            var mixedList = $CoordinatorUIMixin.mixList(response);
            var storedList = $getStore.setList(mixedList);
            $scope.initializeTable(storedList);
        });

        // Get the names of all the owned cohorts so we can display them.
        // We need them for both the owned-school tags in each row, and
        // for the association drop-down.
        var programId;
        if ($scope.$root.level === 'program') {
            programId = $scope.$root.currentEntity.id;
        } else {
            programId = $scope.$root.currentEntity.assc_program_list[0];
        }
        $pertsAjax({
            url: '/api/see/cohort',
            params: {assc_program_list: programId}
        }).then(function (response) {
            $scope.availableCohorts = $seeStore.setList(response);
        });

        $scope.$watch('newAdminCohort', function (cohort) {
            if (!cohort) { return; }
            // A cohort has been selected from the association dropdown.
            // Make the selected users owners of this cohort.
            $scope.$broadcast('/userEntryList/setOwner', cohort.id,
                         $scope.selectedList);

            // Clear the select box so it can be used again.
            $scope.newAdminCohort = undefined;
            // Notify the chosen plugin of the change after the current digest
            // has finished.
            setTimeout(function () {
                $('[chosen-select]').trigger('chosen:updated');
            }, 1);
        });

        $scope.deleteSelectedUsers = function () {
            // Make sure they didn't click by mistake.
            var msg = "Are you sure you want to delete " +
                $scope.selectedList.length + " users?";
            if (!confirm(msg)) { return; }

            // Delete each user one by one.
            $forEachAsync($scope.selectedList, function (userId) {
                return $pertsAjax({url: '/api/delete/' + userId});
            }, 'serial').then(function () {
                // Rebuild the list of displayed users based on which
                // ones weren't just deleted.
                $scope.fullList = forEach($scope.fullList, function (user) {
                    if (!arrayContains($scope.selectedList, user.id)) {
                        return user;
                    }
                });
                // Uncheck all the select boxes.
                $scope.selectedList = [];
            });
        };

        // Build a dialog box for displaying email addresses of selected users.
        $scope.openDialog = function () {
            var testingDialogMarkup = '' +
                '<div class="modal-header">' +
                    '<h3>Email Addresses: paste into "To:" field</h3>' +
                '</div>' +
                '<div class="modal-body">' +
                    '<p>' +
                        arrayUnique(forEach($scope.fullList, function (u) {
                            if (arrayContains($scope.selectedList, u.id)) {
                                return u.login_email;
                            }
                        })).join(', ') +
                    '</p>' +
                '</div>' +
                '<div class="modal-footer">' +
                    '<button ng-click="close()" class="btn">' +
                        'Close' +
                    '</button>' +
                '</div>';
            // See angular-ui docs for details on available options.
            // http://angular-ui.github.io/bootstrap/#/modal
            var modalInstance = $modal.open({
                backdrop: true,
                keyboard: true,
                backdropClick: true,
                backdropFade: true,
                template:  testingDialogMarkup,
                controller: function ($scope, $modalInstance) {
                    $scope.close = function () {
                        $modalInstance.dismiss('close');
                    };
                }
            });
        };

    };
    return {
        scope: {},
        controller: controller,
        templateUrl: '/static/dashboard_widgets/user_entry_list.html'
    };
});

PertsApp.directive('userEntry', function () {
    'use strict';
    var controller = function ($scope, $pertsAjax, $seeStore, $getStore, $window) {
        TableRowController.call(this, $scope, $getStore);

        $scope.$watch('userId', function (userId) {
            if (!userId) { return; }
            $scope.user = $scope.initializeRow(userId);
            $scope.processRelationships();
        }, true);

        $scope.$watch('user.user_type', function (userType) {
            if (userType === 'teacher') {
                $scope.verifiedTooltip = "To verify this administrator, " +
                    "make them the owner of a school.";
            } else {
                $scope.verifiedTooltip = "";
            }
        });

        $scope.$on('/userEntryList/setOwner', function (event, cohortId, selectedUsers) {
            // Don't execute if this broadcast doesn't apply to us.
            if (!arrayContains(selectedUsers, $scope.user.id)) { return; }
            $scope.makeSchoolAdmin(cohortId);
        });

        $scope.processRelationships = function () {
            if (!$scope.user.owned_cohort_list) { return; }
            $scope.ownedCohorts = $seeStore.getList($scope.user.owned_cohort_list);
        };

        $scope.makeSchoolAdmin = function (cohortId) {
            // 1) Make this user a school admin
            // 2) Make them the owner of the specified cohort
            $pertsAjax({
                url: '/api/set_owner/user/' + $scope.user.id +
                     '/cohort/' + cohortId
            }).then(function (user) {
                // Update local data model with new user associations.
                $scope.user = $getStore.set(user);
                $scope.processRelationships();
                // $getStore will save this to the server for us.
                $scope.user.user_type = 'school_admin';
            });
        };

        $scope.disownCohort = function (cohortId) {
            return $pertsAjax({
                url: '/api/disown/user/' + $scope.user.id +
                     '/cohort/' + cohortId
            }).then(function (user) {
                $getStore.set(user);
                $scope.processRelationships();
            });
        };
    };
    return {
        scope: {
            userId: '@userId',
        },
        controller: controller,
        templateUrl: '/static/dashboard_widgets/user_entry.html'
    };
});


// Helps scheduling widgets communicate with each other. Each widget records
// its date with the service. Widgets can also set up callbacks which are
// executed when an activity with the given user type and ordinal changes its
// date. Since multiple activities might meet this description, the latest one
// is provided to the callback.
PertsApp.factory('$scheduleRules', function () {
    'use strict';
    return {
        _d: {},
        _callbacks: {},
        init: function (classroomId, userType, ordinal) {
            forEach([['_d', {}], ['_callbacks', []]], function (i) {
                var p = i[0], v = i[1],
                    blankClassroom = {teacher: {}, student: {}};
                initProp(this[p], classroomId, blankClassroom);
                initProp(this[p][classroomId][userType], ordinal, v);
            }, this);
        },
        addDate: function (activity, date) {
            // record the date
            var classroomId = activity.assc_classroom_list[0];
            var userType = activity.user_type;
            var ordinal = activity.activity_ordinal;

            this.init(classroomId, userType, ordinal);

            var dates = this._d[classroomId][userType][ordinal];
            dates[activity.id] = date;

            // find the latest date from this set
            var latestDate;
            forEach(dates, function (activityId, date) {
                if (latestDate === undefined) {
                    latestDate = date;
                } else if (date > latestDate) {
                    latestDate = date;
                }
            });

            // call the appropriate callbacks
            var callbacks = this._callbacks[classroomId][userType][ordinal];
            forEach(callbacks, function (f) {
                f(latestDate);
            });
        },
        watch: function (classroomId, relativeInfo, callback) {
            var userType = relativeInfo[0];
            var ordinal = relativeInfo[1];

            this.init(classroomId, userType, ordinal);

            this._callbacks[classroomId][userType][ordinal].push(callback);
        }
    };
});

// Will query the server and build appropriate user entry widgets based on
// response.
PertsApp.config(function ($routeProvider) {
    'use strict';
    $routeProvider.when('/:level/:entityId/:page', {
            controller: DashboardController,
            templateUrl: '/static/dashboard_pages/base.html'
        }).otherwise({
            controller: DashboardController,
            templateUrl: '/static/dashboard_pages/base.html'
        });
}).run(function ($seeStore, $getStore) {
    'use strict';
    // Runs every second, sends /api/put calls for updated entities.
    $getStore.watchForUpdates();
    $seeStore.watchForUpdates();
});
