/* Keep native PhotoShow forms and AJAX requests protected after panel refreshes. */
(function () {
    'use strict';
    function token() {
        var meta = document.querySelector('meta[name="photoshow-csrf"]');
        return meta ? meta.content : '';
    }
    if (window.jQuery) {
        jQuery.ajaxPrefilter(function (options) {
            var url = new URL(options.url, location.href);
            if (url.origin !== location.origin) return;
            options.headers = options.headers || {};
            options.headers['X-PhotoShow-CSRF'] = token();
            if (/^(Rig|CTk|Pub|Pri|Logout|Log|Com)$/.test(url.searchParams.get('t') || '') ||
                /^(Upl|Mov|Del|GDe|GEd|AEd|ANw|AGA|AGR|ADe|CDe|GAl|GC|AAc|DTk)$/.test(url.searchParams.get('a') || '')) {
                options.type = 'POST';
            }
        });
    }
    document.addEventListener('click', function (event) {
        var anchor = event.target.closest('a[href]');
        if (!anchor) return;
        var url = new URL(anchor.href, location.href);
        if (url.origin !== location.origin) return;
        if (/^(Rig|CTk|Pub|Pri|Logout|Log|Com)$/.test(url.searchParams.get('t') || '') || url.searchParams.get('a') === 'GDe') {
            event.preventDefault(); event.stopImmediatePropagation();
            var form = document.createElement('form');
            form.method = 'POST'; form.action = url.href;
            var input = document.createElement('input');
            input.type = 'hidden'; input.name = 'csrf'; input.value = token();
            form.appendChild(input); document.body.appendChild(form); form.submit();
        }
    }, true);
}());
