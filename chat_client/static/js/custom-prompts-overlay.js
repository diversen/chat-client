const customPromptsButton = document.getElementById('new-from-custom');
const customPromptsOverlay = document.querySelector('.custom-prompts-overlay');

customPromptsButton.addEventListener('click', async function (event) {
    event.preventDefault();

    // Toggle overlay visibility
    if (customPromptsOverlay.style.display === "none" || customPromptsOverlay.style.display === "") {
        // Show overlay and fetch prompts
        try {
            const response = await fetch('/prompt/json');
            if (!response.ok) {
                throw new Error(`Failed to fetch prompts: ${response.status}`);
            }
            
            const data = await response.json();
            if (data.error) {
                console.error('Error fetching prompts:', data.message);
                return;
            }
            
            // Clear existing content
            const promptsList = customPromptsOverlay.querySelector('.prompts-list');
            promptsList.innerHTML = '';
            
            // Add prompts to overlay
            if (data.prompts && data.prompts.length > 0) {
                data.prompts.forEach(prompt => {
                    const promptLink = document.createElement('a');
                    promptLink.href = `/?id=${prompt.prompt_id}`;
                    promptLink.textContent = prompt.title;
                    promptLink.className = 'prompt-item';
                    promptsList.appendChild(promptLink);
                });
            } else {
                const noPromptsMsg = document.createElement('div');
                noPromptsMsg.textContent = 'No custom prompts available';
                noPromptsMsg.className = 'no-prompts-message';
                promptsList.appendChild(noPromptsMsg);
            }
            
            customPromptsOverlay.style.display = "block";
        } catch (error) {
            console.error('Error loading custom prompts:', error);
        }
    } else {
        // Hide overlay
        customPromptsOverlay.style.display = "none";
    }
});

// Close overlay when clicking outside
document.addEventListener('click', function (event) {
    if (!customPromptsButton.contains(event.target) && !customPromptsOverlay.contains(event.target)) {
        customPromptsOverlay.style.display = "none";
    }
});

// Close overlay on page show (browser back/forward)
window.addEventListener('pageshow', function (e) {
    if (e.persisted) {
        customPromptsOverlay.style.display = "none";
    }
});