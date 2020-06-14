// base.js
//
// The place for PERTS-wide setup and configuration of javascript

// All javascript error reporting comes through this function. It communitcates
// with the app engine logs via /api/log and with Sentry via Raven.

// Because IE sucks, we need to define this. If we turn this to true, it'll turn on
// a bunch of logging. Boo IE, boo.
var debug = false;

function pertsLog(severity, messageDictionary) {
    'use strict';
    // We've encountered some situations where a user's page gets into a loop
    // and sends huge numbers of errors. Prevent that.
    if (!window._pertsErrorCount) {
        window._pertsErrorCount = 0;
    }
    if (window._pertsErrorCount === 10) {
        if (!messageDictionary.message) {
            messageDictionary.message = '';
        }
        messageDictionary.message = "10 ERRORS LOGGED ON THIS PAGE. FUTHER " +
            "ERRORS WILL BE IGNORED.\n" + messageDictionary.message;
    } else if (window._pertsErrorCount > 10) {
        return;
    }
    window._pertsErrorCount += 1;

    // These are all set in base.html; they will at least be empty strings.
    messageDictionary.userId = window.userId;
    messageDictionary.userEmail = window.userEmail;
    messageDictionary.userType = window.userType;

    jQuery.ajax({
        type: "POST",
        url: '/api/log/' + severity,
        contentType: 'application/x-www-form-urlencoded',
        data: messageDictionary
    });


    // Sentry is good at collecting many kinds of info on its own; it doesn't
    // need the whole messageDictionary. Also, user details are configured in
    // base.html on the Raven object.
    var message = messageDictionary.message;
    // Native errors sometimes provide a line number.
    if (messageDictionary.line) {
        message += ' Line: ' + messageDictionary.line;
    }
    // Angular provides nice stack traces, so send them also if available.
    if (messageDictionary.stackTrace) {
        message += ' Stack trace: ' + JSON.stringify(messageDictionary.stackTrace);
    }
    Raven.captureMessage(message, {tags: {userId: messageDictionary.userId}});
}

// Collects browser information and forwards to pertsLog, which logs the error
// with Sentry and the App Engine logs.
// The preferred way to manually log an error without interrupting the user.
window.onerror = function (message, url, line) {
    'use strict';
    if (url === undefined) {
        url = window.location.href;
    }
    pertsLog('info', {
        javascriptError: 'window.onerror',
        message: message,
        url: url,
        line: line,
        href: window.location.href,
        userAgent: window.navigator.userAgent,
        appVersion: window.navigator.appVersion
    });
    if (debug) {console.error(message);}
};

// Add a onkeydown listener that prevents the backspace key from "going back"
// in the browser.
preventBackspaceNavigation();

// ** angular ** //

// This is the base angular app used on all pages
var PertsApp = angular.module(
    'PertsApp',
    ['ui.bootstrap', 'ngSanitize', 'pasvaz.bindonce'],
    function ($interpolateProvider, $tooltipProvider) {
    'use strict';
    // ui.bootstrap.step above is a customized version of accordion used on the
    // teacher panel

    // change the default bracket notation (which is normally {{foo}})
    // so that it doesn't interfere with jinja (server-side templates)
    $interpolateProvider.startSymbol('[[');
    $interpolateProvider.endSymbol(']]');

    // Globally configure tooltips.
    $tooltipProvider.options({
        appendToBody: true
    });
});

// A $http wrapper with lots of convenience:
// 1. Understands the success boolean in all of our responses
// 2. Hooked into an element in the header that shows ajax status and result
// 3. Makes promises
PertsApp.factory('$pertsAjax', function ($http, $q, $window) {
    'use strict';
    // add an ajax wrapper with things like ui notifications and error handling
    return function $pertsAjax(unsafeKwargs) {
        // defaults
        var kwargs = {
            url: '',
            params: {},
            method: 'GET',
            rawResponse: false,
            successMessage: null,
            errorMessage: 'Error, please reload'
        };
        forEach(kwargs, function (k, v) {
            if (unsafeKwargs[k]) {
                kwargs[k] = unsafeKwargs[k];
            }
        });

        // ignore testing and archived entities unless explicitly told otherwise
        if ((kwargs.url.contains('api/get') || kwargs.url.contains('api/see'))) {
            if (kwargs.params.is_test === undefined) {
                kwargs.params.is_test = false;
            }
            if (kwargs.params.is_archived === undefined) {
                kwargs.params.is_archived = false;
            }
        }

        // Problem: we want to be able to set null values to the server, but
        // angular drops these from request strings. E.g. given {a: 1, b: null}
        // angular creates the request string '?a=1'
        // Solution: translate javascript nulls to a special string, which
        // the server will again translate to python None. We use '__null__'
        // because is more client-side-ish, given that js and JSON have a null
        // value.
        // javascript | request string | server
        // -----------|----------------|----------
        // p = null;  | ?p=__null__    | p = None
        forEach(kwargs.params, function (k, v) {
            if (typeof v === 'string' && v.substring(0, 2) === '__') {
                throw new Error("Values prefixed with a double underscore " +
                    "are reserved. See config.py");
            }
            if (v === null) {
                kwargs.params[k] = '__null__';
            }
        });

        var httpKwargs = {
            url: kwargs.url,
            method: kwargs.method
        };

        // Customize the call based on http method.
        if (kwargs.method === 'POST') {
            // Angular puts 'data' in the request body (a.k.a. payload) rather
            // than in the URL, which is the whole point of POSTs.
            httpKwargs.data = kwargs.params;
            httpKwargs.headers = {
                // Required by GAE's implementation of webob.
                'Content-Type': 'application/x-www-form-urlencoded'
            };
        } else if (kwargs.method === 'GET') {
            // Angular puts 'params' in the URL, which is right for GETs.
            httpKwargs.params = kwargs.params;
        }

        // display in the UI that we've started the call
        $window.displayUserMessage('info', "Loading...");

        // Make the call, anticipating the server's use of 'success' to
        // indicate whether or not an error occurred.
        var deferred = $q.defer();
        // The 'success' callback here is in terms of HTTP; the server
        // responded with a 200.
        $http(httpKwargs).success(function (response, status) {
            // The sense of 'success' here is whether any exception was
            // caught during the call.
            if (response.success) {
                if (kwargs.rawResponse) {
                    deferred.resolve(response);
                } else {
                    deferred.resolve(response.data);
                }
                if (kwargs.successMessage) {
                    $window.displayUserMessage('info', kwargs.successMessage);
                }
                $window.clearUserMessage(1200);
            } else {
                if (debug) { console.error(response); }
                deferred.reject(response.message);
                $window.displayUserMessage('error', kwargs.errorMessage);
            }
        }).error(function (response, status) {
            // The sense of 'error' here is in terms of HTTP; the server
            // responded with a 500 or similar.
            if (debug) { console.error(response); }
            deferred.reject(response.message);
            $window.displayUserMessage('error', kwargs.errorMessage);
        });
        return deferred.promise;
    };
});

// By default, AngularJS will catch errors and log them to the Console. We want
// to keep that behavior; however, we want to intercept it so that we can also
// log the errors to the server for later analysis.
PertsApp.provider('$exceptionHandler', {
    $get: function (errorLogService) {
        'use strict';
        return errorLogService;
    }
});

// The error log service is our wrapper around the core error handling ability
// of AngularJS. Notice that we pass off to the native "$log" method and then
// handle our additional server-side logging.
PertsApp.factory('errorLogService', function ($log, $window) {
    'use strict';
    function log(exception, cause) {
        // Pass off the error to the default error handler on the AngualrJS
        // logger. This will output the error to the console (and let the
        // application keep running normally for the user).
        $log.error.apply($log, arguments);

        // Now, we need to try and log the error the server.
        try {
            var errorMessage = exception.toString();
            var stackTrace = $window.printStackTrace({e: exception});

            // Log the JavaScript error to the server with jQuery. Using
            // $pertsAjax, which uses $http, causes a circular dependency in
            // angular.
            $window.pertsLog('info', {
                javascriptError: 'angular',
                url: $window.location.href,
                message: errorMessage,
                stackTrace: stackTrace,
                cause: cause || '',
                userAgent: window.navigator.userAgent,
                appVersion: window.navigator.appVersion
            });
        } catch (loggingError) {
            // For Developers - log the log-failure.
            $log.warn("Error logging failed");
            $log.log(loggingError);
        }
    }

    // Return the logging function.
    return log;
});

PertsApp.factory('$emptyPromise', function ($q) {
    'use strict';
    return function $emptyPromise(valueToPass) {
        // Create an immediately-resolving promise. Used to imitate the
        // promises created by ajax calls, e.g. in program app testing.
        var deferred = $q.defer();
        deferred.resolve(valueToPass);
        return deferred.promise;
    };
});

// A utility function that can run for-like loops with asynchronous processes.
// Use just like forEach, but you can launch something like an ajax call in the
// loop, as long as you return a promise. You can choose to run the calls in
// serial (one after the other) or in parallel (launching them all at once).
// Either way, you can attach a callback when they're all done with .then. For
// example, this would call doAsyncJob() for every item in myList, one after
// the other, and run doSomethingElse() once those were all done:

// $forEachAsync(myList, function (item) {
//     return doAsyncJob(item);
// }, 'serial').then(function () {
//     doSomethingElse();
// });
PertsApp.factory('$forEachAsync', function ($q) {
    'use strict';
    return function forEachAsync(arrayOrDict, f, serialOrParallel) {
        if (serialOrParallel === 'parallel') {
            // Iterate over the data, calling f immediately for each data
            // point. Collect all the resulting promises together for return
            // so further code can be executed when all the calls are done.
            return $q.all(forEach(arrayOrDict, f));
        }
        if (serialOrParallel === 'serial') {
            // Set up a deferred we control as a zeroth link in the chain,
            // which makes writing the loop easier.
            var serialDeferred = $q.defer(),
                serialPromise = serialDeferred.promise;
            // Do NOT make all the calls immediately, instead embed each data
            // point and chain them in a series of 'then's.
            forEach(arrayOrDict, function (a, b) {
                serialPromise = serialPromise.then(f.partial(a, b));
            });
            // Fire off the chain.
            serialDeferred.resolve();
            // Return the whole chain so further code can extend it.
            return serialPromise;
        }
        throw new Error(
            "Must be 'serial' or 'parallel', got " + serialOrParallel
        );
    };
});

// The angularjs-aware equivalent of setInterval().
// Our old version of angular doesn't have this, although newer ones do.
// This should be a decent polyfill in the mean time.
PertsApp.factory('$interval', function ($timeout) {
    'use strict';
    var interval = function interval(f, period) {
        var handle = {};
        var vamp = function () {
            f();
            handle.promise = $timeout(vamp, period);
        };
        handle.promise = $timeout(vamp, period);
        return handle;
    };
    interval.cancel = function (handle) {
        $timeout.cancel(handle.promise);
    };
    return interval;
});

function entityStoreFactory($q, $emptyPromise, $pertsAjax, $timeout, verb) {
    'use strict';
    // The Entity Store

    // DESCRIPTION

    // Serves as a layer between a web app and the PERTS server. Operates
    // strictly by entity ids. Any complicated queries need to be done
    // separately. Ignores property prefixed with an underscore.

    // There are three big advantages to using the store. One is that you can
    // grab a reference to an object even if the related AJAX call isn't yet
    // complete. When the call returns, the properties of that object will be
    // available in your reference with no additional work.

    // The second is that it caches. This means you don't have to worry about
    // being wasteful with calls. Grab something twice, but it will only talk
    // to the server once.

    // The third is that it takes care of updating simple properties. Change a
    // property in your local reference and the store will notice and send an
    // /api/put call for you. This is particularly nice with the angular
    // paradigm. Your widget exposes its data model; the user makes a change;
    // the store notices and updates. You did no work.

    // METHODS

    // .get(entityId)

    // Get a reference to the requested object. Not guaranteed to have any
    // properties right off the bat. But it will, and your reference to it will
    // always be valid when the object changes, no matter when or where from.

    // .set(entity)

    // Save an entity to the store. Overwrites existing data, but does NOT
    // break other widgets' references to this entity, i.e. they all see your
    // changes. Useful when executing a custom query and you want to save the
    // results.
    // Returns the saved entity. Note that the object you use as an argument
    // here is NOT linked to the store, but the returned value IS.

    // .load(id string or array of ids)

    // Load one or many entities from the server and save them to the store.
    // Useful in lists when you know you'll need a large set of data to be
    // available for child widgets.

    // EXAMPLES

    // // I have an id, I want the entity.
    // var myEntity = store.get(id)

    // // I used AJAX to get an entity. I want to save it to the store.
    // var myEntity = store.set(ajaxEntity);

    // // I used AJAX to get a bunch of entities I need. I want to save them
    // // all to the store.
    // var myEntityList = store.setList(ajaxEntityList);

    // // I'm a list widget. I know my children will need a bunch of entities.
    // // I don't need them myself, but I want to load them all at once instead
    // // of having my children make a bunch of individual calls.
    // store.load(allEntityIds);
    // // Now my children can write this:
    // store.getList(myEntityIds);
    // // which will not trigger an ajax calls b/c they've already been cached.

    // // Notice that if the child widget is, for some reason, used OUTSIDE of
    // // a parent list context, this same call will STILL WORK because the
    // // the store will just see that these ids HAVEN'T been loaded and make
    // // an ajax call for you.

    return {
        _m: {},  // client data model
        _cache: {},  // simulation of server state, just like program app
        _failedPuts : 0,
        get: function (id, shouldLoadIfMissing) {
            if (!id) { return; }
            if (this._m[id] === undefined) {
                this._m[id] = {};
                this._cache[id] = {};
            }
            if (shouldLoadIfMissing !== false) {
                this.load(id);
            }
            return this._m[id];
        },
        getList: function (ids) {
            this.load(ids);
            return forEach(ids, function (id) {
                return this.get(id);
            }, this);
        },
        set: function (newEntity) {
            var id = newEntity.id;
            if (this._m[id] === undefined) {
                this._m[id] = {};
                this._cache[id] = {};
            }
            var changedKeys = dictionaryDiff(newEntity, this._m[id]);
            if (changedKeys.length > 0) {
                forEach(changedKeys, function (k) {
                    this._m[id][k] = newEntity[k];
                }, this);
                this._set_cache(id, newEntity);
            }
            return this._m[id];
        },
        setList: function (entities) {
            return forEach(entities, function (e) {
                return this.set(e);
            }, this);
        },
        _set_cache: function (id, newEntity) {
            forEach(newEntity, function(k, v) {
                // we only want to cache primitive properties
                var valid_type = arrayContains(['string', 'number', 'boolean'],
                    typeof v) || v === null;
                var valid_property = !arrayContains(['modified'], k);
                // ignore "private" properties prefixed with an underscore
                var isPrivate = k.substring(0, 1) === '_';
                if (valid_type && valid_property && !isPrivate) {
                    this._cache[id][k] = v;
                }
            }, this);
        },
        load: function (id_or_ids) {
            var ids;
            if (typeof id_or_ids === 'string') {
                ids = [id_or_ids];
            } else {  // assume array
                ids = arrayUnique(id_or_ids);
            }
            var missingIds = [];
            forEach(ids, function (id) {
                // The entity may already be initialized as an empty dictionary
                // in the store, so we can't check for "missing" entities by
                // simply comparing to undefined. Instead, check for the id
                // property because all pegasus entities have an id.
                if (this._m[id] === undefined || this._m[id].id === undefined) {
                    missingIds.push(id);
                }
            }, this);
            // fetch what we don't already have
            if (missingIds.length > 0) {
                // Mark these as pending by setting their id property so that
                // if they're accessed through get() in the meanwhile we don't
                // kick off more ajax calls.
                forEach(missingIds, function (id) {
                    this.set({id: id});
                }, this);
                var store = this;
                return $pertsAjax({
                    url: '/api/' + verb + '_by_ids',
                    method: 'POST',  // use POST to avoid URL length limits
                    params: {ids: missingIds}
                }).then(function (response) {
                    forEach(response, function (entity) {
                        store.set(entity);
                    });
                });
            } else {
                return $emptyPromise();
            }
        },
        synchronize: function () {
            var self = this;
            var promises = [];
            forEach(self._m, function (id, entity) {
                // get changes
                var keysToUpdate = dictionaryDiff(self._cache[id], entity);
                // Ignore keys that may have been introduced into the cache
                // but aren't present in the model. This happens when the
                // server uses abbreviated output formats for specific calls,
                // like /api/get_roster.
                keysToUpdate = keysToUpdate.filter(function (k) {
                    return entity.hasOwnProperty(k);
                });
                if (keysToUpdate.length > 0) {
                    var params = {};
                    forEach(keysToUpdate, function (k) {
                        params[k] = entity[k];
                    });
                    // update server and cache
                    var p = $pertsAjax({
                        url: '/api/put_by_id/' + id,
                        params: params,
                        successMessage: 'saved'
                    }).then(function (response) {
                        // Sometimes the server sees a change to one property
                        // and changes another, so the entity sent back in the
                        // response is different from the one we (the client)
                        // have in the model. But the server is always right,
                        // so save whatever it gives us to both model and
                        // cache.
                        self._set_cache(response.id, response);
                        forEach(response, function (k, v) {
                            // With the one exception of the property the user
                            // is actively working on, for instance if they're
                            // typing in a field. In that case, the model has
                            // newer information than the server.
                            if (k in params) { return; }
                            self._m[response.id][k] = response[k];
                        });
                    });
                    promises.push(p);
                }
            });
            // If any ajax calls were made, return a promise that will resolve
            // when all the calls are complete. Otherwise, return the dummy
            // (immediately-resolving) promise.
            var p = promises.length > 0 ? $q.all(promises) : $emptyPromise();
            // Attach an error callback in case the ajax call fails.
            return p.then(null, function () {
                self._failedPuts += 1;
            });
        },
        watchForUpdates: function () {
            if (this._failedPuts < 10) {
                this.synchronize();
                $timeout(this.watchForUpdates.bind(this), 1000);
            } else {
                window.onerror("Entity store has stopped trying to contact the server.");
                displayUserMessage('error', "Connection lost, please reload.");
            }
        }
    };
}

PertsApp.factory('$seeStore', function ($q, $emptyPromise, $pertsAjax, $timeout) {
    'use strict';
    return entityStoreFactory($q, $emptyPromise, $pertsAjax, $timeout, 'see');
});

PertsApp.factory('$getStore', function ($q, $emptyPromise, $pertsAjax, $timeout) {
    'use strict';
    return entityStoreFactory($q, $emptyPromise, $pertsAjax, $timeout, 'get');
});

PertsApp.directive('ngFocus', function () {
    'use strict';
    return {
        restrict: 'A',
        require: 'ngModel',
        link: function (scope, element, attrs) {
            element.bind('focus', function () {
                scope.$apply(attrs.ngFocus);
            });
        }
    };
});

PertsApp.directive('ngBlur', function () {
    'use strict';
    return {
        restrict: 'A',
        require: 'ngModel',
        link: function (scope, element, attrs) {
            element.bind('blur', function () {
                scope.$apply(attrs.ngBlur);
            });
        }
    };
});

// A directive you can add to select tags to make them look prettier in modern
// browsers (webkit, FF)
// For example, write:
// <select styled-select><option>1</option></select>
// Angular and css does the rest.
PertsApp.directive('styledSelect', function () {
    'use strict';
    return function postLink(scope, element, attr) {
        element.wrap('<div class="styled-select" />');
        element.after('<i></i>');
        var shouldHide = scope.$eval(attr.ngHide) === true ||
                         scope.$eval(attr.ngShow) === false;
        if (shouldHide) {
            element.parent().addClass('ng-hide');
        }
    };
});

// A directive you can add to select tags to make them searchable, i.e. a
// combobox. If you are tying the select to the client data model, you must
// specify the name of the scope variable storing the data. Otherwise the menu
// won't update as the data changes.

// For example, if the select is populated from $scope.myClassrooms, write:

// <select chosen-select select-options="myClassrooms">
//     <option ng-repeat="classroom in myClassrooms" value="[[classroom.id]]">
//         [[classroom.name]]
//     </option>
// </select>

// Documentation: http://harvesthq.github.io/chosen/
PertsApp.directive('chosenSelect', function () {
    'use strict';
    return function postLink(scope, element, attr) {
        // If selectOptions is set as an attribute of the select element, then
        // we assume the menu is populated from that scope variable. Watch it
        // for changes and trigger the chosen plugin to update in response.
        if (attr.selectOptions) {
            scope.$watch(attr.selectOptions, function (options) {
                element.trigger("chosen:updated");
            }, true);
        }

        // Watch to see if angular enables or disabled the select, and tell
        // the chosen widget to check itself.
        attr.$observe('disabled', function (disabled) {
            element.trigger("chosen:updated");
        });

        // Angular does funny stuff like add empty option tags in certain
        // cases. Make sure chosen is notified if this happens.
        scope.$watch(function () {
            return element[0].length;
        }, function (newvalue, oldvalue) {
            if (newvalue !== oldvalue) {
                element.trigger("chosen:updated");
            }
        });

        // Activate the chosen plugin on this select element (it's already
        // been wrapped by jQuery!).
        element.chosen({
            // Default search behavior is weird and only matches from the
            // beginning of words. This sets it to search anywhere within the
            // string. See full options available here:
            // http://harvesthq.github.io/chosen/options.html
            search_contains: true
        });
    };
});

// Some handy input-transforming so that it's easier for users to write valid
// text fields.
PertsApp.directive('toLowerCase', function () {
    // http://stackoverflow.com/questions/14419651/angularjs-filters-on-ng-model-in-an-input
    'use strict';
    return {
        require: 'ngModel',
        link: function (scope, element, attrs, modelCtrl) {
            modelCtrl.$parsers.push(function (inputValue) {
                if (!(typeof inputValue === 'string')) { return inputValue; }
                var transformedInput = inputValue.toLowerCase();
                if (transformedInput !== inputValue) {
                    modelCtrl.$setViewValue(transformedInput);
                    modelCtrl.$render();
                }
                return transformedInput;
            });
        }
    };
});

PertsApp.directive('toUpperCase', function () {
    // http://stackoverflow.com/questions/14419651/angularjs-filters-on-ng-model-in-an-input
    'use strict';
    return {
        require: 'ngModel',
        link: function (scope, element, attrs, modelCtrl) {
            modelCtrl.$parsers.push(function (inputValue) {
                if (!(typeof inputValue === 'string')) { return inputValue; }
                var transformedInput = inputValue.toUpperCase();
                if (transformedInput !== inputValue) {
                    modelCtrl.$setViewValue(transformedInput);
                    modelCtrl.$render();
                }
                return transformedInput;
            });
        }
    };
});

// Takes out anything besides upper and lower case letters and spaces
PertsApp.directive('alphaOnly', function () {
    'use strict';
    return {
        require: 'ngModel',
        link: function (scope, element, attrs, modelCtrl) {
            modelCtrl.$parsers.push(function (inputValue) {
                var transformedInput = inputValue.replace(/[^a-zA-Z ]/g, '');
                if (transformedInput !== inputValue) {
                    modelCtrl.$setViewValue(transformedInput);
                    modelCtrl.$render();
                }
                return transformedInput;
            });
        }
    };
});

// turns off when the cloaked elements turn on
PertsApp.directive('cloakMask', function () {
    'use strict';
    return {
        link: function (scope, element, attrs, modelCtrl) {
            element.addClass('ng-hide');
        }
    };
});

// Requires the autogrow textarea jquery plugin.
PertsApp.directive('autogrow', function () {
    'use strict';
    return {link: function (scope, element) {
        element.autogrow();
    }};
});

// An angular-aware version of native confirm()
// Usage: <button ng-confirm-message="Are you sure?"
//                ng-confirm-click="takeAction()">
PertsApp.directive('ngConfirm', [function() {
    'use strict';
    return {
        restrict: 'A',
        link: function(scope, element, attrs) {
            element.bind('click', function() {
                var message = scope.$eval(attrs.ngConfirmMessage);
                if (message && confirm(message)) {
                    scope.$apply(attrs.ngConfirmClick);
                }
            });
        }
    };
}]);

PertsApp.directive('ngTrim', function() {
    'use strict';
    return {
        require: 'ngModel',
        priority: 300,
        link: function(scope, iElem, iAttrs, ngModel) {
            if (iAttrs.ngTrim === 'false') {
                // Be careful here. We override any value comming from the previous
                // parsers to return the real value in iElem
                ngModel.$parsers.unshift(function() {
                    return iElem.val();
                });
            }
        }
    };
});
