/**
 * mcads Image Maximizer
 * Adds click functionality to X-ray images to maximize them in an overlay
 */
document.addEventListener('DOMContentLoaded', function() {
    // Select all regular X-ray images (not visualization images which have their own handlers)
    const xrayImages = document.querySelectorAll('.img-fluid:not(.visualization-image)');
    
    xrayImages.forEach(img => {
        // Add the xray-image class for styling
        img.classList.add('xray-image');
        
        // Create the click handler function to maximize the image
        const maximizeImage = function() {
            // Create overlay elements
            const overlay = document.createElement('div');
            overlay.style.position = 'fixed';
            overlay.style.top = '0';
            overlay.style.left = '0';
            overlay.style.width = '100%';
            overlay.style.height = '100%';
            overlay.style.backgroundColor = 'rgba(0, 0, 0, 0.9)';
            overlay.style.display = 'flex';
            overlay.style.alignItems = 'center';
            overlay.style.justifyContent = 'center';
            overlay.style.zIndex = '9999';
            overlay.style.cursor = 'zoom-out';
            
            // Create expanded image
            const expandedImg = document.createElement('img');
            expandedImg.src = img.src;
            expandedImg.style.maxHeight = '90vh';
            expandedImg.style.maxWidth = '90vw';
            expandedImg.style.objectFit = 'contain';
            
            // Copy the filter style from the original image to preserve effects like invert
            if (img.style.filter) {
                expandedImg.style.filter = img.style.filter;
            }
            
            // Add close functionality
            overlay.addEventListener('click', function() {
                document.body.removeChild(overlay);
            });
            
            // Prevent click on image from closing the overlay
            expandedImg.addEventListener('click', function(e) {
                e.stopPropagation();
            });
            
            // Add keyboard navigation (Escape to close)
            const escKeyHandler = function(e) {
                if (e.key === 'Escape' && document.body.contains(overlay)) {
                    document.body.removeChild(overlay);
                    document.removeEventListener('keydown', escKeyHandler);
                }
            };
            document.addEventListener('keydown', escKeyHandler);
            
            // Append elements to the body
            overlay.appendChild(expandedImg);
            document.body.appendChild(overlay);
        };
        
        // Add click event listener to the image
        img.addEventListener('click', maximizeImage);
        
        // Also add click event to the parent container if it exists
        const container = img.closest('.position-relative');
        if (container) {
            // Ensure the container has pointer cursor
            container.style.cursor = 'pointer';
            
            // Add click event to the container
            container.addEventListener('click', function(e) {
                // Don't trigger if clicking on a child button or link
                if (e.target.tagName !== 'BUTTON' && e.target.tagName !== 'A') {
                    maximizeImage();
                }
            });
        }
    });
}); 