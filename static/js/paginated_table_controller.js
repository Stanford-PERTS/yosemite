// Abstracts the functionality of Yosemite tables which are always the same:
// * Selecting
// * Sorting
// * Searching
// * Pagination

// Remember to change $scope.selectedUsers or selectedWhatever to selectedList.
// sometimes its in the markup!

// Also remember to change userList, activityList whatever to fullList

function PaginatedTableController($scope) {
    'use strict';

    // Inheriting controllers must define:
    // $scope.columns = [ /* ...varies... */ ];

    // Inheriting controllers may define:
    // $scope.additionalSearchRules(), takes and returns a (potentially
    //     modified) searchList.
    // $scope.pageSize, default is 50.

    // Inheriting controllers must call:
    // $scope.initializeTable(), providing an array of entities to display
    //     in the table. Entities must have a UIMixin applied first.
    // $scope.createSearchData(), if data relevant to search, but not part of
    //     the row entities themselves, changes.

    // Inheriting controllers may call:
    // $scope.turnOffSelection() to kill all watchers related to selection.

    $scope.pageSize = 50;
    $scope.pageIndex = 0;  // current page displayed
    $scope.emptyTableMessage = "Loading...";

    $scope.fullList = [];
    $scope.searchList = [];  // search-matched subset of the full list
    $scope.selectedList = [];  // those whose checkbox is checked
    $scope.pageList = [];  // the things actually shown in the UI
    $scope.reverseSort = undefined;  // will be boolean if user sorts
    $scope.sortedColumn = undefined;  // will be int (index of columns array)

    // Scan through the fullList and keep only those matching the search text.
    // Searching doesn't look at objects directly; see $createSearchData().
    var search = function(searchText) {
        console.debug("search()", searchText);
        if (!searchText) {
            $scope.searchList = $scope.fullList;
        } else {
            $scope.searchList = forEach($scope.fullList, function (entity) {
                if (entity._searchText.contains(searchText.toLowerCase())) {
                    console.debug("...found in", entity._searchText.replace(/\s/g, ' '));
                    return entity;
                }
                else { console.debug("...not found"); }
            });
        }

        // Allow the specific controller to do additional filtering of the
        // matching entities, e.g. for makeups.
        if (typeof $scope.additionalSearchRules === 'function') {
            $scope.searchList = $scope.additionalSearchRules($scope.searchList);
        }

        // Re-calculate what goes on this page based on the new search results.
        $scope.setPage(0);
    };
    // Obviously, run search any time the search text changes.
    $scope.$watch('searchText', search);
    // It's also critical to re-run search any time the $scope.fullList
    // changes, so that changes propagate to searchList, which sets the page,
    // and thus propagates to pageList, which actually drives the UI.
    $scope.$watch('fullList', function () {
        console.debug("$watch fullList");
        search($scope.searchText);
    });

    $scope.initializeTable = function (entityList) {
        console.debug("initializeTable()");
        $scope.searchList = $scope.fullList = entityList;
        $scope.createSearchData();
        search();
        // Now that loading is done, if the ng-repeat in the table markup
        // has nothing to display, it will show this message.
        $scope.emptyTableMessage = 'Nothing to show';
    };

    $scope.createSearchData = function () {
        forEach($scope.fullList, function (e) { e.createSearchData(); });
    };

    $scope.setPage = function (pageIndex) {
        console.debug("setPage()", pageIndex, "current index:", $scope.pageIndex);
        if (pageIndex < 0) { pageIndex = 0; }
        // Use floor not ceil because pageIndex counts from zero.
        var lastPageIndex = Math.floor($scope.searchList.length / $scope.pageSize);
        if (pageIndex === 'last' || pageIndex > lastPageIndex) {
            pageIndex = lastPageIndex;
        }
        $scope.pageIndex = pageIndex;
        $scope.pageList = $scope.searchList.slice(
            pageIndex * $scope.pageSize, (pageIndex + 1) * $scope.pageSize);
        console.debug("new index:", $scope.pageIndex, "slicing at:", pageIndex * $scope.pageSize, (pageIndex + 1) * $scope.pageSize);
    };
    // I don't think I need this b/c I explicitly call setPage() in every case
    // $scope.$watch('pageIndex', $scope.setPage);

    $scope.pageRange = function () {
        return range(Math.ceil($scope.searchList.length / $scope.pageSize));
    };

    $scope.sortBy = function (colIndex) {
        var column = $scope.columns[colIndex];

        // Only provide sorting on columns marked sortable.
        if (!column.sortable) { return; }

        if ($scope.reverseSort === undefined) {
            $scope.reverseSort = false;
        }
        if ($scope.sortedColumn === colIndex) {
            $scope.reverseSort = !$scope.reverseSort;
        }

        // If things are being slow, we might not have cached the search data
        // by the time someone searches/sorts. Allow for its absence w/o error.
        if (
          $scope.fullList.length === 0 ||
          $scope.fullList[0]._searchObject === undefined
        ) { return; }

        // The stability of javascript sorting is implementation-depedendent.
        // http://blog.8thlight.com/will-warner/2013/03/26/stable-sorting-in-ruby.html
        // http://stackoverflow.com/questions/3026281/array-sort-sorting-stability-in-different-browsers
        // We can ensure stable sorting by sorting otherwise-equal elements
        // by their original position in the list. So determine those original
        // positions here.
        forEach($scope.fullList, function (entity, position) {
            entity._originalPosition = position;
        });
        var sortFunc = function (a, b) {
            var A = a._searchObject[column.colClass];
            var B = b._searchObject[column.colClass];

            if (isStringNumeric(A, 'strict') && isStringNumeric(B, 'strict')) {
                // Are A and B numeric? If so, compare them as numbers, b/c
                // '10' > '100', but 100 > 10.
                A = +A;
                B = +B;
            } else if (typeof A === 'string') {
                // Otherwise compare them as strings in lower case.
                A = A.toLowerCase();
                B = B.toLowerCase();
            } else {
                // Anything that isn't a number or a string should be treated
                // like an empty string (e.g. NaN, null, undefined).
                A = B = '';
            }

            var direction = $scope.reverseSort ? -1 : 1;
            if (A < B) { return direction * -1; }
            if (A > B) { return direction; }

            // These elements appear equal. To ensure stable sorting, sort by
            // their original position before the sort started.
            return (a._originalPosition - b._originalPosition) * direction;
        };
        // Watchers on $scope.fullList will spread the news of this sorting change
        // to $scope.searchList and pageList.
        $scope.fullList.sort(sortFunc);

        // Force an alteration to the reference to make the UI respond via a
        // $watch.
        $scope.fullList = $scope.fullList.slice(0);

        $scope.sortedColumn = colIndex;
    };

    $scope.trackSelection = function (event, entityId, isSelected) {
        if (
            isSelected === true &&
            !arrayContains($scope.selectedList, entityId)
        ) {
            $scope.selectedList.push(entityId);
        } else if (isSelected === false) {
            arrayRemove($scope.selectedList, entityId);
        }
    };
    // Listen to rows whose checkboxes change and track them.
    var selectionChangeOff = $scope.$on(
        '/row/selectionChange', $scope.trackSelection);

    $scope.toggleSelectAll = function (checked) {
        $scope.$broadcast('/table/toggleSelectAll', checked);
    };

    $scope.turnOffSelection = function () {
        selectionChangeOff();
    };
}
