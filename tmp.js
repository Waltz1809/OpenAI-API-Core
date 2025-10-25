let logContent = '';

function log(message) {
    logContent += `[${new Date().toLocaleTimeString()}] ${message}\n`;
    const logContainer = document.getElementById('logContainer');
    const logContentDiv = document.getElementById('logContent');
    logContainer.style.display = 'block';
    logContentDiv.innerHTML = logContent.replace(/\n/g, '<br>');
    logContentDiv.scrollTop = logContentDiv.scrollHeight;
}

function updateProgress(percent, text) {
    document.querySelector('.progress-container').style.display = 'block';
    document.getElementById('progressBar').style.width = percent + '%';
    document.getElementById('progressText').textContent = text;
}

async function convertEpubToTxt() {
    const fileInput = document.getElementById('epubFile');
    const convertBtn = document.getElementById('convertBtn');
    
    if (!fileInput.files[0]) {
        alert('Please select an EPUB file first!');
        return;
    }

    const file = fileInput.files[0];
    if (!file.name.toLowerCase().endsWith('.epub')) {
        alert('Please select a valid EPUB file!');
        return;
    }

    // Get selected image handling option
    const imageHandling = document.querySelector('input[name="imageHandling"]:checked').value;
    log(`Image handling mode: ${imageHandling}`);

    convertBtn.disabled = true;
    logContent = '';
    
    try {
        log('Starting EPUB to TXT conversion...');
        updateProgress(10, 'Reading EPUB file...');
        
        const arrayBuffer = await file.arrayBuffer();
        const zip = await JSZip.loadAsync(arrayBuffer);
        
        log('EPUB file loaded successfully');
        updateProgress(20, 'Parsing table of contents...');
        
        // Parse TOC
        const tocData = await parseTOC(zip);
        log(`Found ${tocData.chapters.length} chapters in TOC`);
        
        updateProgress(40, 'Extracting content from HTML files...');
        
        // Extract content according to TOC
        const chaptersContent = await extractChapterContent(zip, tocData, imageHandling);
        log(`Extracted content from ${Object.keys(chaptersContent).length} chapters`);
        
        updateProgress(70, 'Creating TXT files...');
        
        // Create output ZIP with TXT files
        const outputZip = new JSZip();
        let imageFiles = {};
        let allUploadedUrls = {};
        
        // Collect all images first for upload processing
        for (const [chapterTitle, contentData] of Object.entries(chaptersContent)) {
            const content = typeof contentData === 'string' ? contentData : contentData.content;
            const images = typeof contentData === 'object' ? contentData.images : {};
            
            if (content && content.trim() && images && Object.keys(images).length > 0) {
                Object.assign(imageFiles, images);
            }
        }
        
        // Upload images if upload mode is selected
        if (imageHandling === 'upload' && Object.keys(imageFiles).length > 0) {
            updateProgress(75, 'Uploading images to server...');
            log(`Starting upload of ${Object.keys(imageFiles).length} images in batches of 2...`);
            allUploadedUrls = await uploadImageBatch(imageFiles);
            log(`Upload completed. ${Object.keys(allUploadedUrls).length} images processed.`);
        }

        let chapterIndex = 1;
        for (const [chapterTitle, contentData] of Object.entries(chaptersContent)) {
            // Handle both old string format and new object format for backward compatibility
            let content = typeof contentData === 'string' ? contentData : contentData.content;
            const images = typeof contentData === 'object' ? contentData.images : {};
            
            if (content && content.trim()) {
                // Replace image placeholders with direct links if upload mode
                if (imageHandling === 'upload' && Object.keys(allUploadedUrls).length > 0) {
                    content = replaceImagePlaceholders(content, allUploadedUrls);
                }
                
                const filename = `${chapterIndex}.txt`;
                outputZip.file(filename, content);
                log(`Created: ${filename}`);
                
                chapterIndex++;
            }
        }
        
        // Skip adding image files to ZIP in upload mode since we use direct links
        updateProgress(90, 'Generating download...');
        
        const blob = await outputZip.generateAsync({type: 'blob'});
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = file.name.replace('.epub', '_chapters.zip');
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        updateProgress(100, 'Conversion completed!');
        log('Conversion completed successfully. Download should start automatically.');
        
    } catch (error) {
        log('Error: ' + error.message);
        alert('Error converting EPUB: ' + error.message);
    } finally {
        convertBtn.disabled = false;
    }
}

async function parseTOC(zip) {
    try {
        // First, find the container.xml to get the OPF file
        const containerFile = zip.file('META-INF/container.xml');
        if (!containerFile) {
            throw new Error('Invalid EPUB: container.xml not found');
        }
        
        const containerXml = await containerFile.async('text');
        const parser = new DOMParser();
        const containerDoc = parser.parseFromString(containerXml, 'text/xml');
        
        const opfPath = containerDoc.querySelector('rootfile').getAttribute('full-path');
        log(`Found OPF file: ${opfPath}`);
        
        // Get the OPF file
        const opfFile = zip.file(opfPath);
        if (!opfFile) {
            throw new Error('OPF file not found');
        }
        
        const opfXml = await opfFile.async('text');
        const opfDoc = parser.parseFromString(opfXml, 'text/xml');
        
        // Extract spine order
        const spineItems = Array.from(opfDoc.querySelectorAll('spine itemref'));
        const manifestItems = Array.from(opfDoc.querySelectorAll('manifest item'));
        
        // Create a map of id to href
        const manifestMap = {};
        manifestItems.forEach(item => {
            manifestMap[item.getAttribute('id')] = item.getAttribute('href');
        });
        
        // Try to find NCX or navigation document for chapter titles
        let chapters = [];
        
        // Try to find NCX file
        const ncxItem = manifestItems.find(item => 
            item.getAttribute('media-type') === 'application/x-dtbncx+xml'
        );
        
        if (ncxItem) {
            const ncxPath = getFullPath(opfPath, ncxItem.getAttribute('href'));
            const ncxFile = zip.file(ncxPath);
            if (ncxFile) {
                const ncxXml = await ncxFile.async('text');
                const ncxDoc = parser.parseFromString(ncxXml, 'text/xml');
                
                const navPoints = Array.from(ncxDoc.querySelectorAll('navPoint'));
                chapters = navPoints.map((navPoint, index) => {
                    const label = navPoint.querySelector('navLabel text');
                    const content = navPoint.querySelector('content');
                    const title = label ? label.textContent.trim() : `Chapter ${index + 1}`;
                    const href = content ? content.getAttribute('src').split('#')[0] : null;
                    
                    return {
                        title: title,
                        href: href,
                        files: []
                    };
                });
                
                log(`Found ${chapters.length} chapters in NCX`);
            }
        }
        
        // If no chapters found from NCX, create chapters from spine
        if (chapters.length === 0) {
            log('No NCX found, creating chapters from spine order');
            let chapterIndex = 1;
            
            spineItems.forEach(spineItem => {
                const idref = spineItem.getAttribute('idref');
                const href = manifestMap[idref];
                
                if (href && href.endsWith('.html') || href.endsWith('.xhtml')) {
                    chapters.push({
                        title: `Chapter ${chapterIndex}`,
                        href: href,
                        files: [href]
                    });
                    chapterIndex++;
                }
            });
        }
        
        // Map files to chapters based on spine order
        if (chapters.length > 0 && chapters[0].files.length === 0) {
            let currentChapterIndex = 0;
            
            spineItems.forEach(spineItem => {
                const idref = spineItem.getAttribute('idref');
                const href = manifestMap[idref];
                
                if (href && (href.endsWith('.html') || href.endsWith('.xhtml'))) {
                    // Find which chapter this file belongs to
                    let belongsToChapter = currentChapterIndex;
                    
                    for (let i = 0; i < chapters.length; i++) {
                        if (chapters[i].href === href) {
                            belongsToChapter = i;
                            currentChapterIndex = i;
                            break;
                        }
                    }
                    
                    if (belongsToChapter < chapters.length) {
                        chapters[belongsToChapter].files.push(href);
                    }
                }
            });
        }
        
        return {
            chapters: chapters,
            basePath: opfPath.substring(0, opfPath.lastIndexOf('/') + 1)
        };
        
    } catch (error) {
        log('Error parsing TOC: ' + error.message);
        throw error;
    }
}

function getFullPath(basePath, relativePath) {
    const baseDir = basePath.substring(0, basePath.lastIndexOf('/') + 1);
    return baseDir + relativePath;
}

async function findAndExtractAllImages(zip, tocData) {
    const allImages = {};
    
    // Get all files in the ZIP
    const allFiles = Object.keys(zip.files);
    
    // Filter for image files
    const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg'];
    const imageFiles = allFiles.filter(filePath => {
        const extension = filePath.toLowerCase().substring(filePath.lastIndexOf('.'));
        return imageExtensions.includes(extension) && !zip.files[filePath].dir;
    });
    
    log(`Found ${imageFiles.length} image files in EPUB`);
    
    // Extract all found images
    for (const imagePath of imageFiles) {
        try {
            const filename = imagePath.split('/').pop();
            const imageFile = zip.file(imagePath);
            if (imageFile) {
                const imageData = await imageFile.async('blob');
                allImages[filename] = imageData;
                log(`Cataloged image: ${filename} from ${imagePath}`);
            }
        } catch (error) {
            log(`Error cataloging image ${imagePath}: ${error.message}`);
        }
    }
    
    return allImages;
}

async function extractChapterContent(zip, tocData, imageHandling = 'no-images') {
    const chaptersContent = {};
    
    // First, find and extract ALL images in the EPUB for upload mode
    let allAvailableImages = {};
    if (imageHandling === 'upload') {
        allAvailableImages = await findAndExtractAllImages(zip, tocData);
        log(`Cataloged ${Object.keys(allAvailableImages).length} total images for potential upload`);
    }
    
    for (const chapter of tocData.chapters) {
        log(`Processing chapter: ${chapter.title}`);
        let chapterText = '';
        let allH1Texts = [];
        let chapterImages = {};
        
        const filesToProcess = chapter.files.length > 0 ? chapter.files : [chapter.href];
        
        for (const href of filesToProcess) {
            if (!href) continue;
            
            const fullPath = tocData.basePath + href;
            const htmlFile = zip.file(fullPath) || zip.file(href);
            
            if (htmlFile) {
                try {
                    const htmlContent = await htmlFile.async('text');
                    const result = await extractTextFromHtml(htmlContent, zip, tocData.basePath, imageHandling, allAvailableImages);
                    const { h1Texts, bodyText, images } = result || {};
                    
                    if (h1Texts && Array.isArray(h1Texts)) {
                        allH1Texts.push(...h1Texts);
                    }
                    if (bodyText && bodyText.trim()) {
                        chapterText += bodyText + '\n\n';
                        log(`Extracted text from: ${href}`);
                    }
                    // Collect images for this chapter
                    if (images && typeof images === 'object') {
                        Object.assign(chapterImages, images);
                    }
                } catch (error) {
                    log(`Error processing ${href}: ${error.message}`);
                }
            } else {
                log(`File not found: ${href}`);
            }
        }
        
        if (chapterText.trim() || allH1Texts.length > 0) {
            // Compare TOC title with h1 texts
            const finalTitle = getTitleForChapter(chapter.title, allH1Texts);
            chaptersContent[chapter.title] = {
                content: finalTitle + '\n\n' + chapterText.trim(),
                images: chapterImages
            };
        }
    }
    
    return chaptersContent;
}

async function extractTextFromHtml(htmlContent, zip, basePath, imageHandling = 'no-images', allAvailableImages = {}) {
    try {
        const parser = new DOMParser();
        const doc = parser.parseFromString(htmlContent, 'text/html');
        
        let h1Texts = [];
        let bodyText = '';
        let images = {};
        
        // Extract h1 tags first
        const h1Elements = doc.querySelectorAll('h1');
        h1Elements.forEach(h1 => {
            const text = processRubyTags(h1).trim();
            if (text) {
                h1Texts.push(text);
            }
        });
        
        // Handle images based on the selected mode BEFORE extracting text
        if (imageHandling === 'no-images') {
            // Remove all image tags for no-images mode
            const imgElements = doc.querySelectorAll('img, image');
            imgElements.forEach(img => img.remove());
        } else if (imageHandling === 'placeholder') {
            // Convert images to placeholder format
            const imgElements = doc.querySelectorAll('img, image');
            imgElements.forEach(img => {
                let imagePath = '';
                
                // Extract image path from different attributes
                if (img.tagName.toLowerCase() === 'img') {
                    imagePath = img.getAttribute('src');
                } else if (img.tagName.toLowerCase() === 'image') {
                    imagePath = img.getAttribute('xlink:href') || img.getAttribute('href');
                }
                
                if (imagePath) {
                    const filename = extractFilename(imagePath);
                    const newImg = doc.createElement('img');
                    newImg.setAttribute('src', filename);
                    img.parentNode.replaceChild(newImg, img);
                }
            });
        } else if (imageHandling === 'upload') {
            // For upload mode, use the pre-extracted images and ensure all images are available
            const imgElements = doc.querySelectorAll('img, image');
            for (const img of imgElements) {
                let imagePath = '';
                
                if (img.tagName.toLowerCase() === 'img') {
                    imagePath = img.getAttribute('src');
                } else if (img.tagName.toLowerCase() === 'image') {
                    imagePath = img.getAttribute('xlink:href') || img.getAttribute('href');
                }
                
                if (imagePath) {
                    const filename = extractFilename(imagePath);
                    
                    // Ensure this image is available for upload
                    if (allAvailableImages[filename]) {
                        images[filename] = allAvailableImages[filename];
                    } else {
                        // Try to extract it if not found
                        const extracted = await extractImageFile(zip, basePath, imagePath, filename, images);
                        if (extracted && images[filename]) {
                            // Add to allAvailableImages for future reference
                            allAvailableImages[filename] = images[filename];
                        }
                    }
                    
                    const newImg = doc.createElement('img');
                    newImg.setAttribute('src', filename); // Use filename placeholder for now
                    img.parentNode.replaceChild(newImg, img);
                }
            }
        }
        
        // Now extract text with processed images
        // First try to get text from specific styled p tags
        const pElements = doc.querySelectorAll('p[style*="opacity:0.4"], p[style*="opacity: 0.4"]');
        if (pElements.length > 0) {
            pElements.forEach(p => {
                const text = processElementWithImages(p).trim();
                if (text) {
                    bodyText += text + '\n\n';
                }
            });
        } else {
            // If no specific styled p tags found, try all p tags
            const allPElements = doc.querySelectorAll('p');
            if (allPElements.length > 0) {
                allPElements.forEach(p => {
                    const text = processElementWithImages(p).trim();
                    if (text) {
                        bodyText += text + '\n\n';
                    }
                });
            } else {
                // If no p tags found, extract from body directly
                const bodyElement = doc.querySelector('body') || doc.documentElement;
                if (bodyElement) {
                    const text = processElementWithImages(bodyElement).trim();
                    if (text) {
                        bodyText = text;
                    }
                }
            }
        }
        
        return { h1Texts, bodyText, images };
    } catch (error) {
        console.error('Error in extractTextFromHtml:', error);
        return { h1Texts: [], bodyText: '', images: {} };
    }
}

function processElementWithImages(element) {
    // Clone the element to avoid modifying the original
    const clonedElement = element.cloneNode(true);
    
    // Remove script and style elements
    const scriptsAndStyles = clonedElement.querySelectorAll('script, style, head, title');
    scriptsAndStyles.forEach(el => el.remove());
    
    // Process ruby tags first
    const rubyElements = clonedElement.querySelectorAll('ruby');
    rubyElements.forEach(ruby => {
        const rb = ruby.querySelector('rb');
        const rt = ruby.querySelector('rt');
        
        if (rb && rt) {
            const rbText = rb.textContent.trim();
            const rtText = rt.textContent.trim();
            
            // Replace the ruby element with rb(rt) format
            const replacementText = document.createTextNode(`${rbText}(${rtText})`);
            ruby.parentNode.replaceChild(replacementText, ruby);
        }
    });
    
    // Convert img elements to text representation (all images should now be img tags)
    const imgElements = clonedElement.querySelectorAll('img');
    imgElements.forEach(img => {
        const src = img.getAttribute('src');
        if (src) {
            const imgText = document.createTextNode(`<img src="${src}"/>`);
            img.parentNode.replaceChild(imgText, img);
        }
    });
    
    // Get the text content and clean up whitespace
    let text = clonedElement.textContent || clonedElement.innerText || '';
    
    // Clean up extra whitespace but preserve line breaks for img tags
    text = text.replace(/\s+/g, ' ').trim();
    
    return text;
}

async function processImages(doc, zip, basePath, imageHandling, images) {
    // Handle both HTML img tags and SVG image tags
    const imgElements = doc.querySelectorAll('img, image');
    
    for (const img of imgElements) {
        let imagePath = '';
        
        // Extract image path from different attributes
        if (img.tagName.toLowerCase() === 'img') {
            imagePath = img.getAttribute('src');
        } else if (img.tagName.toLowerCase() === 'image') {
            imagePath = img.getAttribute('xlink:href') || img.getAttribute('href');
        }
        
        if (!imagePath) continue;
        
        // Extract filename from path
        const filename = extractFilename(imagePath);
        
        if (imageHandling === 'placeholder') {
            // Convert to simple img tag with filename
            const newImg = doc.createElement('img');
            newImg.setAttribute('src', filename);
            img.parentNode.replaceChild(newImg, img);
            
        } else if (imageHandling === 'upload') {
            // Extract the actual image file
            await extractImageFile(zip, basePath, imagePath, filename, images);
            
            // Replace with simple img tag pointing to extracted file
            const newImg = doc.createElement('img');
            newImg.setAttribute('src', `images/${filename}`);
            img.parentNode.replaceChild(newImg, img);
        }
    }
}

function extractFilename(imagePath) {
    // Handle different path formats and extract filename
    const pathWithoutFragment = imagePath.split('#')[0];
    const pathParts = pathWithoutFragment.split('/');
    let filename = pathParts[pathParts.length - 1];
    
    // Handle cases where path starts with ../
    if (filename.includes('../')) {
        const parts = filename.split('../');
        filename = parts[parts.length - 1];
    }
    
    return filename || 'unknown.jpg';
}

async function extractImageFile(zip, basePath, imagePath, filename, images) {
    try {
        // Try different path combinations to find the image
        const possiblePaths = [
            basePath + imagePath,
            imagePath,
            imagePath.replace('../', ''),
            imagePath.replace('../', basePath),
            'OEBPS/' + imagePath,
            'OEBPS/' + imagePath.replace('../', ''),
            'OEBPS/images/' + filename,
            'OEBPS/Images/' + filename,
            'OEBPS/image/' + filename,
            'OEBPS/Image/' + filename,
            'images/' + filename,
            'Images/' + filename,
            'image/' + filename,
            'Image/' + filename,
            'item/image/' + filename,
            'item/images/' + filename,
            'text/' + filename,
            filename // Direct filename in root
        ];
        
        for (const path of possiblePaths) {
            const imageFile = zip.file(path);
            if (imageFile) {
                const imageData = await imageFile.async('blob');
                images[filename] = imageData;
                log(`Extracted image: ${filename} from ${path}`);
                return true;
            }
        }
        
        // If not found by path, search through all files in zip
        const allFiles = Object.keys(zip.files);
        const matchingFiles = allFiles.filter(filePath => {
            const pathFilename = filePath.split('/').pop();
            return pathFilename === filename;
        });
        
        if (matchingFiles.length > 0) {
            const foundPath = matchingFiles[0];
            const imageFile = zip.file(foundPath);
            if (imageFile) {
                const imageData = await imageFile.async('blob');
                images[filename] = imageData;
                log(`Found and extracted image: ${filename} from ${foundPath}`);
                return true;
            }
        }
        
        log(`Image not found: ${imagePath} (filename: ${filename})`);
        return false;
    } catch (error) {
        log(`Error extracting image ${imagePath}: ${error.message}`);
        return false;
    }
}

function processRubyTags(element) {
    // Clone the element to avoid modifying the original
    const clonedElement = element.cloneNode(true);
    
    // Find all ruby elements
    const rubyElements = clonedElement.querySelectorAll('ruby');
    
    rubyElements.forEach(ruby => {
        const rb = ruby.querySelector('rb');
        const rt = ruby.querySelector('rt');
        
        if (rb && rt) {
            const rbText = rb.textContent.trim();
            const rtText = rt.textContent.trim();
            
            // Replace the ruby element with rb(rt) format
            const replacementText = document.createTextNode(`${rbText}(${rtText})`);
            ruby.parentNode.replaceChild(replacementText, ruby);
        }
    });
    
    return clonedElement.textContent;
}

function getTitleForChapter(tocTitle, h1Texts) {
    // Normalize function to compare titles
    function normalize(text) {
        return text.toLowerCase()
            .replace(/[^\w\s]/g, '')
            .replace(/\s+/g, ' ')
            .trim();
    }
    
    const normalizedTocTitle = normalize(tocTitle);
    
    // Check if any h1 text matches TOC title
    const matchingH1 = h1Texts.find(h1Text => 
        normalize(h1Text) === normalizedTocTitle
    );
    
    if (matchingH1) {
        // If TOC title matches h1, use only one (prefer h1 for exact case)
        return matchingH1;
    } else if (h1Texts.length > 0) {
        // If different, use TOC title first, then h1 texts
        return tocTitle + '\n' + h1Texts.join('\n');
    } else {
        // No h1 found, use TOC title only
        return tocTitle;
    }
}

async function uploadImageBatch(imageFiles, filenames) {
    const apiKey = "6d207e02198a847aa98d0a2a901485a5";
    const apiUrl = "https://cors.moldich.eu.org/?q=https://freeimage.host/api/1/upload";
    const uploadedUrls = {};
    
    // Process images in batches of 5
    const batchSize = 5;
    const imageEntries = Object.entries(imageFiles);
    const totalImages = imageEntries.length;
    let uploadedCount = 0;
    let successCount = 0;
    
    log(`Total images to upload: ${totalImages}`);
    
    for (let i = 0; i < imageEntries.length; i += batchSize) {
        const batch = imageEntries.slice(i, i + batchSize);
        const batchNumber = Math.floor(i / batchSize) + 1;
        const totalBatches = Math.ceil(totalImages / batchSize);
        
        log(`Processing batch ${batchNumber}/${totalBatches} (${batch.length} images)`);
        updateProgress(75 + (i / totalImages) * 10, `Uploading batch ${batchNumber}/${totalBatches}...`);
        
        const uploadPromises = [];
        
        for (const [filename, imageBlob] of batch) {
            const uploadPromise = uploadSingleImage(apiUrl, apiKey, filename, imageBlob);
            uploadPromises.push(uploadPromise);
        }
        
        try {
            const results = await Promise.all(uploadPromises);
            results.forEach((result, index) => {
                const [filename] = batch[index];
                uploadedCount++;
                
                if (result.success) {
                    successCount++;
                    uploadedUrls[filename] = result.url;
                    log(`✓ [${uploadedCount}/${totalImages}] ${filename} -> ${result.url}`);
                } else {
                    log(`✗ [${uploadedCount}/${totalImages}] Failed: ${filename} - ${result.error}`);
                    // Keep original filename as fallback
                    uploadedUrls[filename] = filename;
                }
            });
            
            // Update progress with current status
            const progressPercent = 75 + (uploadedCount / totalImages) * 10;
            updateProgress(progressPercent, `Uploaded ${successCount}/${uploadedCount} images (${uploadedCount}/${totalImages} processed)`);
            
            // Add small delay between batches to avoid rate limiting
            if (i + batchSize < imageEntries.length) {
                log(`Waiting 1 second before next batch...`);
                await new Promise(resolve => setTimeout(resolve, 1000));
            }
        } catch (error) {
            log(`Batch upload error: ${error.message}`);
            // Keep original filenames as fallback
            batch.forEach(([filename]) => {
                uploadedCount++;
                uploadedUrls[filename] = filename;
                log(`✗ [${uploadedCount}/${totalImages}] Error: ${filename} - using filename as fallback`);
            });
        }
    }
    
    const finalSuccessRate = ((successCount / totalImages) * 100).toFixed(1);
    log(`Upload completed: ${successCount}/${totalImages} images uploaded successfully (${finalSuccessRate}%)`);
    updateProgress(85, `Upload completed: ${successCount}/${totalImages} images uploaded (${finalSuccessRate}%)`);
    
    return uploadedUrls;
}

async function uploadSingleImage(apiUrl, apiKey, filename, imageBlob) {
    try {
        const formData = new FormData();
        formData.append('source', imageBlob, filename);
        formData.append('key', apiKey);
        formData.append('action', 'upload');
        formData.append('format', 'json');
        
        const response = await fetch(apiUrl, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.status_code === 200 && result.success) {
            return { success: true, url: result.image.url };
        } else {
            return { success: false, error: result.status_txt || 'Unknown error' };
        }
    } catch (error) {
        return { success: false, error: error.message };
    }
}

function replaceImagePlaceholders(content, uploadedUrls) {
    let updatedContent = content;
    
    // Replace <img src="filename.jpg"/> with <img src="direct_url"/>
    for (const [filename, url] of Object.entries(uploadedUrls)) {
        const placeholder = `<img src="${filename}"/>`;
        const replacement = `<img src="${url}"/>`;
        updatedContent = updatedContent.replace(new RegExp(escapeRegExp(placeholder), 'g'), replacement);
        
        // Also handle images/ folder format
        const folderPlaceholder = `<img src="images/${filename}"/>`;
        updatedContent = updatedContent.replace(new RegExp(escapeRegExp(folderPlaceholder), 'g'), replacement);
    }
    
    return updatedContent;
}

function escapeRegExp(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function sanitizeFilename(filename) {
    return filename
        .replace(/[<>:"/\\|?*]/g, '')
        .replace(/\s+/g, '_')
        .substring(0, 100);
}