/* make JSLint complain less */
/*jslint browser: true*/
/*globals alert, confirm, prompt, console, $, jQuery, angular, forEach, noop*/
/*globals dictionaryDiff, arrayUnique, Mousetrap, userType*/

/* 
Keyboard shortcuts

Are rather easy to build with the mousetrap library [1]. 
Mousetrap and this file are included in base and so
these shortcuts are global.

Perts short cuts should begin with 'p p' by convention.

[1] http://craig.is/killing/mice
*/

if (normalUserType === 'god' || normalUserType === 'researcher') {
    // Admin tools
    // Hide or show administrative controls with a keyboard shortcut
    Mousetrap.bind('p p a', function () {
        'use strict';
        $('.admin-control').toggle("fast");
        $('#search').focus();
    });

    // hide
    Mousetrap.bind('esc', function () {
        'use strict';
        $('.admin-control').hide("fast");
    });

    // Show extra information, like entity ids, on dashboard.
    Mousetrap.bind('p p i', function () {
        'use strict';
        $('.id-display').toggle("fast");
    });
}
