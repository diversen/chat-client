/* 

Very basic flash messages for server-side and javascript.

// Flash messages looks like this:
<div class="flash-messages">
	<div class="flash flash-error">Email eller password er ikke korrekt.</div>
</div>

// Remove flash messages on page load
<script type="module">
    import { Flash } from "/static/js/flash.js";

	// Allow multiple messages to be displayed at the same time (default is false)
	Flash.singleMessage = false
	
	// Default is to keep messages until user clicks on them
	// Clean messages after 5 seconds - default is null 
	Flash.removeAfterSecs = 5;

	// Clear messages visible on page load
    Flash.clearMessages();
	// Comment out if you want to keep the messages until user clicks on them

	// Set a flash message
	Flash.setMessage('This is a flash message', 'success');

	// Will add a div to "flash-messages" 
	// With the classes "flash flash-success random_..." and remove it after 5 seconds

	// Flash.setMessage('This is a flash message', 'success');
	// Will add a div to "flash-messages" with the classes "flash flash-success"

	// Remove messages set by server-side languages after 5 seconds
	// Flash.clearMessages();

</script>

*/

class Flash {

	/**
	 * If true, clear the message element before adding a new message
	 * This means only one message can be displayed at a time
	 */
	static singleMessage = true;

	/**
	 * 
	 */
    static removeAfterSecs = null;

	/**
	 * Set a flash message in the DOM. Based on singleMessage, it will either clear the message element or not
	 * Based on removeAfterSecs, it will remove the message after a set amount of seconds
	 */
    static setMessage(message, type) {
        const messageElem = document.querySelector(".flash-messages");
        messageElem.focus();

		if (this.singleMessage) {
        	messageElem.innerHTML = '';
		}

        if (!type) {
            type = 'notice';
        }

        let class_random = 'random_' + (Math.random() + 1).toString(36).substring(2);
        if (this.removeAfterSecs) {
            class_random = 'random_' + (Math.random() + 1).toString(36).substring(2);
            setTimeout(function () {
                let elem = document.querySelector('.' + class_random)
                if (elem) {
                    elem.remove();
                }
            }, this.removeAfterSecs * 1000)
        }

        const html = `<div class="flash flash-${type} ${class_random}">${message}</div>`;
        messageElem.insertAdjacentHTML('afterbegin', html);
    }

    /**
     * Remove all flash messages
	 * This is meant for removing messages on page load, set by server-side languages 
     */
    static clearMessages() {
		if (this.removeAfterSecs) {
			setTimeout(function () {
				// Remove all flash messages that are static. Set by server-side languages
				let elems = document.querySelectorAll('.flash-static')
				elems.forEach(function (elem) {
					elem.remove();
				})
			}, this.removeAfterSecs * 1000)
		}
    }
}

document.addEventListener("click", function (e) {
    if (e.target.classList.contains('flash')) {
        e.target.remove();
    }
})

export { Flash }