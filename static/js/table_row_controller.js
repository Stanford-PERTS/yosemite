// Abstracts the functionality of Yosemite tables rows:
// * Selecting
// * Searching

function TableRowController($scope, $getStore) {
    'use strict';

    // Inheriting controllers must define:
    // $scope.toSearchObject(), takes the row's entity and converts it to a
    //     simple dictionary object of searchable values. See $createSearchData

    // Inheriting controllers may define:
    // ...

    // Inheriting controllers must call:
    // $scope.initializeRow() with the string id of the row entity
    // $scope.createSearchData() when any data other than the row entity itself
    //     referenced by toSearchObject changes.

    // Inheriting controllers may call:
    // $scope.turnOffSelection() to kill all watchers related to selection.

    var entity = {id: undefined};

    $scope.initializeRow = function (id) {
        entity = $getStore.get(id, false);  // don't load if missing
        return entity;
    };

    $scope.$watch(function () { return entity; }, function (e) {
        if (e.createSearchData) { e.createSearchData(); }
    }, true);

    // Announce changes to the selected checkbox to the table.
    var isSelectedOff = $scope.$watch('isSelected', function (isSelected) {
        $scope.$emit('/row/selectionChange', entity.id, isSelected);
    });

    var selectAllOff = $scope.$on('/table/toggleSelectAll', function (event, checked) {
        $scope.isSelected = checked;
    });

    $scope.turnOffSelection = function () {
        isSelectedOff();
        selectAllOff();
    };
}
