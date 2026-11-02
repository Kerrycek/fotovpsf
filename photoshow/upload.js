/* Original dropzone appearance with native file selection and protected POST. */
function init_dropzone() {
    document.querySelectorAll('form.dropzone').forEach(function (form) {
        var input = form.querySelector('input[type="file"]');
        if (!input || form.dataset.nativeUploadReady) return;
        form.dataset.nativeUploadReady = '1';
        var submit = form.querySelector('button');
        var hint = form.querySelector('div:last-child');
        var choose = document.createElement('button');
        choose.type = 'button'; choose.className = 'file_upload';
        choose.textContent = hint ? hint.textContent : 'Upload images here';
        choose.addEventListener('click', function () { input.click(); });
        input.accept = 'image/jpeg,image/png,image/gif';
        input.setAttribute('aria-label', 'Photographs');
        form.insertBefore(choose, input);
        input.style.display = 'none';
        if (submit) submit.style.display = 'none';
        if (hint) hint.style.display = 'none';
        function upload() {
            if (!input.files.length) return;
            choose.disabled = true; choose.textContent = 'Uploading…';
            form.requestSubmit(submit);
        }
        input.addEventListener('change', upload);
        choose.addEventListener('dragover', function (event) { event.preventDefault(); choose.classList.add('file_upload_highlight'); });
        choose.addEventListener('dragleave', function () { choose.classList.remove('file_upload_highlight'); });
        choose.addEventListener('drop', function (event) {
            event.preventDefault(); choose.classList.remove('file_upload_highlight');
            input.files = event.dataTransfer.files; upload();
        });
    });
}
document.addEventListener('DOMContentLoaded', init_dropzone);
if (window.jQuery) jQuery(document).ajaxComplete(init_dropzone);
