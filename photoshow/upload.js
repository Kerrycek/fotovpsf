/* Native multiple-file upload; retains the original PHP handler and CSRF form. */
function init_dropzone() {
    document.querySelectorAll('form.dropzone').forEach(function (form) {
        var input = form.querySelector('input[type="file"]');
        if (!input) return;
        if (form.dataset.nativeUploadReady) return;
        form.dataset.nativeUploadReady = '1';
        input.accept = 'image/jpeg,image/png,image/gif';
        input.setAttribute('aria-label', 'Fotografie k nahrání');
        var choose = document.createElement('button');
        choose.type = 'button'; choose.textContent = 'Vybrat fotografie';
        choose.addEventListener('click', function () { input.click(); });
        var selection = document.createElement('p');
        selection.className = 'upload-selection'; selection.setAttribute('aria-live', 'polite');
        input.parentNode.insertBefore(choose, input);
        input.parentNode.insertBefore(selection, input.nextSibling);
        input.style.display = 'none';
        input.addEventListener('change', function () { selection.textContent = 'Vybrané soubory: ' + input.files.length; });
        var submit = form.querySelector('button:not([type=button])');
        if (submit) submit.textContent = 'Nahrát fotografie';
        var hint = form.querySelector('div:last-child');
        if (hint) hint.textContent = 'Můžeš vybrat více fotografií najednou. JPEG, PNG nebo GIF; dohromady nejvýše 64 MB.';
    });
}

document.addEventListener("DOMContentLoaded", init_dropzone);
if (window.jQuery) jQuery(document).ajaxComplete(init_dropzone);
