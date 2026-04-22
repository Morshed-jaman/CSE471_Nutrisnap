(function () {
    const imageInput = document.getElementById('image');
    const imagePreview = document.getElementById('imagePreview');
    const imagePreviewWrap = document.getElementById('imagePreviewWrap');
    const dropZone = document.getElementById('uploadDropZone');
    const fileHint = document.getElementById('uploadFileHint');

    if (!imageInput || !imagePreview || !dropZone || !fileHint || !imagePreviewWrap) {
        return;
    }

    function resetPreview() {
        imagePreview.src = '';
        imagePreviewWrap.classList.add('d-none');
        dropZone.classList.remove('has-file');
        fileHint.textContent = 'Click to browse or drag and drop';
    }

    function setPreview(file) {
        if (!file) {
            resetPreview();
            return;
        }

        fileHint.textContent = `Selected: ${file.name}`;
        dropZone.classList.add('has-file');

        if (!file.type.startsWith('image/')) {
            imagePreviewWrap.classList.add('d-none');
            return;
        }

        const reader = new FileReader();
        reader.onload = (event) => {
            imagePreview.src = event.target?.result || '';
            imagePreviewWrap.classList.remove('d-none');
        };
        reader.readAsDataURL(file);
    }

    imageInput.addEventListener('change', (event) => {
        const file = event.target.files?.[0];
        setPreview(file);
    });

    ['dragenter', 'dragover'].forEach((eventName) => {
        dropZone.addEventListener(eventName, (event) => {
            event.preventDefault();
            event.stopPropagation();
            dropZone.classList.add('is-dragover');
        });
    });

    ['dragleave', 'drop'].forEach((eventName) => {
        dropZone.addEventListener(eventName, (event) => {
            event.preventDefault();
            event.stopPropagation();
            dropZone.classList.remove('is-dragover');
        });
    });
})();
