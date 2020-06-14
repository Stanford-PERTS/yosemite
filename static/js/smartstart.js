// Borrowed from the SmartStart theme from themeforest.net
// Applies to things like the animated social media icons in the footer,
// and the drop down nav menus in the header.

// Run the whole thing on a jQuery document ready event.
$(function () {

    /* ---------------------------------------------------------------------- */
    /*  Main Navigation
    /* ---------------------------------------------------------------------- */

    var $mainNav    = $('#main-nav').children('ul'),
        optionsList = '<option value="" selected>Navigate...</option>';

    // Regular nav
    $mainNav.on('mouseenter', 'li', function() {
        var $this    = $(this),
            $subMenu = $this.children('ul');
        if( $subMenu.length ) $this.addClass('hover');
        $subMenu.hide().stop(true, true).fadeIn(200);
    }).on('mouseleave', 'li', function() {
        $(this).removeClass('hover').children('ul').stop(true, true).fadeOut(50);
    });

    // Responsive nav
    $mainNav.find('li').each(function() {
        var $this   = $(this),
            $anchor = $this.children('a'),
            depth   = $this.parents('ul').length - 1,
            indent  = '';

        if( depth ) {
            while( depth > 0 ) {
                indent += ' - ';
                depth--;
            }
        }

        optionsList += '<option value="' + $anchor.attr('href') + '">' + indent + ' ' + $anchor.text() + '</option>';
    }).end()
      .after('<select class="responsive-nav">' + optionsList + '</select>');

    $('.responsive-nav').on('change', function() {
        window.location = $(this).val();
    });

    /* end Main Navigation */

    /* ---------------------------------------------------------------------- */
    /*  Min-height
    /* ---------------------------------------------------------------------- */

    // Set minimum height so footer will stay at the bottom of the window, even if there isn't enough content
    window.setMinHeight = function () {

        $('#content').css('min-height',
            $(window).outerHeight(true)
            - ( $('body').outerHeight(true)
            - $('body').height() )
            - $('#header').outerHeight(true)
            - ( $('#content').outerHeight(true) - $('#content').height() )
            + ( $('.page-title').length ? Math.abs( parseInt( $('.page-title').css('margin-top') ) ) : 0 )
            - $('#footer').outerHeight(true)
            - $('#footer-bottom').outerHeight(true)
        );
    };

    // Init
    setMinHeight();

    // Window resize
    $(window).on('resize', function() {

        var timer = window.setTimeout( function() {
            window.clearTimeout( timer );
            setMinHeight();
        }, 30 );

    });

    /* end Min-height */
});

