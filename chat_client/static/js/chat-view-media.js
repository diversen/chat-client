function formatAttachmentSize(sizeBytes) {
    const size = Number(sizeBytes || 0);
    if (!Number.isFinite(size) || size <= 0) return '';
    if (size >= 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)}MB`;
    if (size >= 1024) return `${Math.round(size / 1024)}KB`;
    return `${size}B`;
}

function isImageAttachment(attachment = {}) {
    const contentType = String(attachment?.content_type || '').trim().toLowerCase();
    const fileName = String(attachment?.name || '').trim().toLowerCase();
    if (contentType.startsWith('image/')) return true;
    return /\.(png|jpe?g|gif|webp|bmp|svg)$/i.test(fileName);
}

function getAttachmentPreviewUrl(attachmentId) {
    return `/api/chat/attachments/${attachmentId}/preview`;
}

function createMessageImages(images = [], { onOpenImagePreview }) {
    if (!Array.isArray(images) || images.length === 0) return null;

    const preview = document.createElement('div');
    preview.className = 'image-preview';

    images.forEach((image, index) => {
        const dataUrl = String(image?.data_url || '').trim();
        if (!dataUrl.startsWith('data:image/')) return;

        const item = document.createElement('div');
        item.className = 'upload-preview-tile message-image-tile';

        const tileButton = document.createElement('button');
        tileButton.type = 'button';
        tileButton.className = 'upload-preview-open';
        tileButton.title = `Preview attached image ${index + 1}`;
        tileButton.setAttribute('aria-label', `Preview attached image ${index + 1}`);
        tileButton.addEventListener('click', () => {
            onOpenImagePreview(dataUrl, tileButton.title);
        });

        const thumbnail = document.createElement('img');
        thumbnail.className = 'message-image-thumb';
        thumbnail.alt = `Message image ${index + 1}`;
        thumbnail.src = dataUrl;

        tileButton.appendChild(thumbnail);
        item.appendChild(tileButton);
        preview.appendChild(item);
    });

    if (preview.children.length === 0) return null;
    return preview;
}

function createMessageAttachments(attachments = [], options = {}) {
    const {
        removable = false,
        onRemove = null,
        onOpenAttachmentPreview = null,
    } = options;

    if (!Array.isArray(attachments) || attachments.length === 0) return null;

    const preview = document.createElement('div');
    preview.className = 'attachment-preview';

    attachments.forEach((attachment) => {
        if (isImageAttachment(attachment)) return;
        const attachmentId = String(attachment?.attachment_id || attachment?.id || '');
        const fileName = String(attachment?.name || 'attachment');
        const fileExtension = (fileName.split('.').pop() || 'file').slice(0, 6).toUpperCase();
        const item = document.createElement('div');
        item.className = 'upload-preview-tile message-attachment-tile';

        const tileButton = document.createElement(attachmentId ? 'button' : 'div');
        if (attachmentId) {
            tileButton.type = 'button';
            tileButton.title = `Preview ${fileName}`;
            tileButton.setAttribute('aria-label', `Preview ${fileName}`);
            tileButton.addEventListener('click', () => {
                if (typeof onOpenAttachmentPreview === 'function') {
                    onOpenAttachmentPreview(attachmentId);
                }
            });
        }
        tileButton.className = 'upload-preview-open';

        const meta = document.createElement('div');
        meta.className = 'upload-preview-meta';

        const kind = document.createElement('span');
        kind.className = 'upload-preview-kind';
        kind.textContent = fileExtension;
        meta.appendChild(kind);

        const name = document.createElement('span');
        name.className = 'upload-preview-name';
        name.textContent = fileName;
        meta.appendChild(name);

        const sizeText = formatAttachmentSize(attachment?.size_bytes || attachment?.size);
        if (sizeText) {
            const size = document.createElement('span');
            size.className = 'upload-preview-size';
            size.textContent = sizeText;
            meta.appendChild(size);
        }

        tileButton.appendChild(meta);
        item.appendChild(tileButton);

        if (removable) {
            const remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'image-preview-remove';
            remove.textContent = '×';
            remove.setAttribute('aria-label', `Remove ${name.textContent}`);
            remove.addEventListener('click', () => {
                if (typeof onRemove === 'function') {
                    onRemove(attachmentId);
                }
            });
            item.appendChild(remove);
        }

        preview.appendChild(item);
    });

    return preview.children.length ? preview : null;
}

function createMessageMediaPreview(images = [], attachments = [], options = {}) {
    const {
        onOpenImagePreview = null,
        onOpenAttachmentPreview = null,
        onRemovePendingImage = null,
        onRemovePendingAttachment = null,
        removableImages = false,
        removableAttachments = false,
    } = options;

    if (!Array.isArray(images) || !Array.isArray(attachments) || (!images.length && !attachments.length)) {
        return null;
    }

    const preview = document.createElement('div');
    preview.className = 'image-preview';

    images.forEach((image, index) => {
        const imageId = String(image?.id || '');
        const imageName = String(image?.name || `image ${index + 1}`);
        const item = document.createElement('div');
        item.className = removableImages ? 'upload-preview-tile' : 'upload-preview-tile message-image-tile';

        const tileButton = document.createElement('button');
        tileButton.type = 'button';
        tileButton.className = 'upload-preview-open';
        tileButton.title = removableImages ? `Preview ${imageName}` : `Preview attached image ${index + 1}`;
        tileButton.setAttribute('aria-label', removableImages ? `Preview ${imageName}` : `Preview attached image ${index + 1}`);
        tileButton.addEventListener('click', () => {
            if (typeof onOpenImagePreview === 'function') {
                const dataUrl = removableImages ? String(image?.dataUrl || '') : String(image?.data_url || '').trim();
                onOpenImagePreview(dataUrl, removableImages ? imageName : tileButton.title);
            }
        });

        const thumbnail = document.createElement('img');
        thumbnail.className = removableImages ? 'upload-preview-thumb' : 'message-image-thumb';
        thumbnail.alt = removableImages ? imageName : `Message image ${index + 1}`;
        thumbnail.src = removableImages ? String(image?.dataUrl || '') : String(image?.data_url || '').trim();
        if (!String(thumbnail.src).startsWith('data:image/')) {
            return;
        }

        tileButton.appendChild(thumbnail);
        if (removableImages) {
            const meta = document.createElement('div');
            meta.className = 'upload-preview-meta';

            const kindElement = document.createElement('span');
            kindElement.className = 'upload-preview-kind';
            kindElement.textContent = 'IMAGE';
            meta.appendChild(kindElement);

            const nameElement = document.createElement('span');
            nameElement.className = 'upload-preview-name';
            nameElement.textContent = imageName;
            meta.appendChild(nameElement);

            const sizeText = formatAttachmentSize(image?.size);
            if (sizeText) {
                const sizeElement = document.createElement('span');
                sizeElement.className = 'upload-preview-size';
                sizeElement.textContent = sizeText;
                meta.appendChild(sizeElement);
            }

            tileButton.appendChild(meta);
        }

        item.appendChild(tileButton);

        if (removableImages) {
            const remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'image-preview-remove';
            remove.title = `Remove ${imageName}`;
            remove.setAttribute('aria-label', `Remove ${imageName}`);
            remove.textContent = '×';
            remove.addEventListener('click', () => {
                if (typeof onRemovePendingImage === 'function') {
                    onRemovePendingImage(imageId);
                }
            });
            item.appendChild(remove);
        }

        preview.appendChild(item);
    });

    attachments.forEach((attachment, index) => {
        if (!isImageAttachment(attachment)) return;

        const attachmentId = String(attachment?.attachment_id || attachment?.id || '');
        if (!attachmentId) return;

        const imageName = String(attachment?.name || `attached image ${index + 1}`);
        const previewUrl = getAttachmentPreviewUrl(attachmentId);
        const item = document.createElement('div');
        item.className = removableAttachments ? 'upload-preview-tile' : 'upload-preview-tile message-image-tile';

        const tileButton = document.createElement('button');
        tileButton.type = 'button';
        tileButton.className = 'upload-preview-open';
        tileButton.title = removableAttachments ? `Preview ${imageName}` : `Preview attached image ${index + 1}`;
        tileButton.setAttribute('aria-label', removableAttachments ? `Preview ${imageName}` : `Preview attached image ${index + 1}`);
        tileButton.addEventListener('click', () => {
            if (typeof onOpenImagePreview === 'function') {
                onOpenImagePreview(previewUrl, imageName);
            }
        });

        const thumbnail = document.createElement('img');
        thumbnail.className = removableAttachments ? 'upload-preview-thumb' : 'message-image-thumb';
        thumbnail.alt = removableAttachments ? imageName : `Message image ${index + 1}`;
        thumbnail.src = previewUrl;
        tileButton.appendChild(thumbnail);

        if (removableAttachments) {
            const meta = document.createElement('div');
            meta.className = 'upload-preview-meta';

            const kindElement = document.createElement('span');
            kindElement.className = 'upload-preview-kind';
            kindElement.textContent = 'IMAGE';
            meta.appendChild(kindElement);

            const nameElement = document.createElement('span');
            nameElement.className = 'upload-preview-name';
            nameElement.textContent = imageName;
            meta.appendChild(nameElement);

            const sizeText = formatAttachmentSize(attachment?.size_bytes || attachment?.size);
            if (sizeText) {
                const sizeElement = document.createElement('span');
                sizeElement.className = 'upload-preview-size';
                sizeElement.textContent = sizeText;
                meta.appendChild(sizeElement);
            }

            tileButton.appendChild(meta);
        }

        item.appendChild(tileButton);

        if (removableAttachments) {
            const remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'image-preview-remove';
            remove.textContent = '×';
            remove.setAttribute('aria-label', `Remove ${imageName}`);
            remove.addEventListener('click', () => {
                if (typeof onRemovePendingAttachment === 'function') {
                    onRemovePendingAttachment(attachmentId);
                }
            });
            item.appendChild(remove);
        }

        preview.appendChild(item);
    });

    const attachmentPreview = createMessageAttachments(attachments, {
        removable: removableAttachments,
        onRemove: onRemovePendingAttachment,
        onOpenAttachmentPreview,
    });
    if (attachmentPreview) {
        while (attachmentPreview.firstChild) {
            preview.appendChild(attachmentPreview.firstChild);
        }
    }

    return preview.children.length ? preview : null;
}

function createPendingUploadsPreview(pendingUploadsElem, images = [], attachments = [], handlers = {}) {
    const {
        onOpenImagePreview = null,
        onOpenAttachmentPreview = null,
        onRemovePendingImage = null,
        onRemovePendingAttachment = null,
    } = handlers;

    if (!Array.isArray(images) || !Array.isArray(attachments) || (!images.length && !attachments.length)) {
        pendingUploadsElem.innerHTML = '';
        pendingUploadsElem.classList.add('hidden');
        return;
    }

    pendingUploadsElem.classList.remove('hidden');
    pendingUploadsElem.innerHTML = '';

    const preview = createMessageMediaPreview(images, attachments, {
        onOpenImagePreview,
        onOpenAttachmentPreview,
        onRemovePendingImage,
        onRemovePendingAttachment,
        removableImages: true,
        removableAttachments: true,
    });
    if (preview) {
        pendingUploadsElem.appendChild(preview);
    }
}

export {
    createMessageImages,
    createMessageAttachments,
    createMessageMediaPreview,
    createPendingUploadsPreview,
    formatAttachmentSize,
};
