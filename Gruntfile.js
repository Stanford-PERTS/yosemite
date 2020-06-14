// Yosemite Gruntfile.
// CAM 2015-04-06

// Combines and compresses javascript to minimize time taken by synchronous
// http calls during page load. Creates three combined files:
//
// * base.min.js - most of the js requried in the base template, used on
//   every page.
// * dashboard.min.js - js only used on the dashbaord
// * programs.min.js - js only used in the program app
//
// First concatenates files in a specified order to preserve dependencies
// and references between the scripts. Then compresses them with uglify,
// notably without variable renaming (see comments below).

module.exports = function (grunt) {

    // Project configuration.
    grunt.initConfig({
        pkg: grunt.file.readJSON('package.json'),
        concat: {
            options: {
                separator: '\n\n'
            },
            base_js: {
                // The files to concatenate.
                src: [
                    'static/js/stacktrace.js',
                    'static/js/modernizr-2.6.2-custom.min.js',
                    'static/js/json2.js',
                    'static/js/util.js',
                    'static/js/jquery-1.10.2.js',
                    'static/js/chosen.jquery.min.js',
                    'static/js/jquery-autogrow_textarea.js',
                    'static/js/placeholder.js',
                    'static/js/angular-1.0.7.min.js',
                    'static/js/angular-sanitize-1.0.7.min.js',
                    'static/js/bind_once.js',
                    'static/js/angular-ui-bootstrap-0.6.0.min.js',
                    'static/js/mousetrap.min.js',
                    'static/js/keyboardShortcuts.js',
                    'static/js/base.js',
                    'static/js/smartstart.js'
                ],
                // The location of the resulting JS file.
                dest: 'static/js/dist/base.layer.js'
            },
            dashboard_js: {
                src: [
                    // As long as grunt is run via the default task, which
                    // calls the whole 'concat' task at once, then the
                    // concat:base_js subtask will run BEFORE this one,
                    // propagating changes in the base layer into the dashboard
                    // layer.
                    'static/js/dist/base.layer.js',
                    'static/js/datepickr.js',
                    'static/js/paginated_table_controller.js',
                    'static/js/table_row_controller.js',
                    'static/js/dashboard.js'
                ],
                dest: 'static/js/dist/dashboard.layer.js'
            },
            programs_js: {
                src: [
                    'static/js/hashchange.js',
                    'static/js/programs.js',
                    'static/js/gplus-youtubeembed.js'
                ],
                dest: 'static/js/dist/programs.layer.js'
            },
            base_css: {
                // The files to concatenate.
                src: [
                    'static/css/bootstrap.min.css',
                    // bootstrap not included here b/c it messes up includes
                    // and fonts.
                    // 'static/fonts/font-awesome/css/font-awesome.min.css',
                    'static/css/chosen.css',
                    'static/css/smartstart.css',
                    'static/css/main.css'
                ],
                // The location of the resulting file.
                dest: 'static/css/dist/base.layer.css'
            }
        },
        uglify: {
            options: {
                // Unfortunately, we didn't use function parameter annotation
                // syntax in angular, so we can't mangle variables, otherwise
                // angular won't be able to inspect them and inject them
                // properly.
                mangle: false
            },
            base_js: {
                options: {
                    banner: '/* Base layer. Built <%= grunt.template.today() %>. */'
                },
                // The files to concatenate and minify
                src: 'static/js/dist/base.layer.js',
                // The location of the resulting JS file.
                dest: 'static/js/dist/base.min.js'
            },
            dashboard_js: {
                options: {
                    banner: '/* Dashboard layer. Built <%= grunt.template.today() %>. */'
                },
                src: 'static/js/dist/dashboard.layer.js',
                dest: 'static/js/dist/dashboard.min.js'
            },
            programs_js: {
                options: {
                    banner: '/* Programs layer. Built <%= grunt.template.today() %>. */'
                },
                src: 'static/js/dist/programs.layer.js',
                dest: 'static/js/dist/programs.min.js'
            }
        },
        cssmin: {
            options: {
                // Remove all comments.
                keepSpecialComments: 0
            },
            base_css: {
                options: {
                    banner: '/* Base layer. Built <%= grunt.template.today() %>. */'
                },
                src: 'static/css/dist/base.layer.css',
                dest: 'static/css/dist/base.min.css'
            }
        }
    });

    grunt.loadNpmTasks('grunt-contrib-cssmin');
    grunt.loadNpmTasks('grunt-contrib-concat');
    grunt.loadNpmTasks('grunt-contrib-uglify');

    // Default task(s).
    grunt.registerTask('default', ['concat', 'uglify', 'cssmin']);

};
