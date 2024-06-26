(function() {
    const nameContractPairs = [];
    const nameRegex = /Name:\s*(.*\(.*\) \(.*GEM\))/;
    // const contractRegex = /Contract:\s*([^\s]+pump)/;
    const contractRegex = /Contract:\s*([^\s]+)/;


    async function sendContractPairsToServer(pair) {
        try {
            const response = await fetch('http://127.0.0.1:5000/save_contracts', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(pair),
            });
            const result = await response.json();
            console.log(`Server response: ${JSON.stringify(result)}`);
        } catch (error) {
            console.error('Error sending contract pair to server:', error);
        }
    }

    function extractDataFromElement(element) {
        const textContent = element.innerText;
        const nameMatch = textContent.match(nameRegex);
        const contractMatch = textContent.match(contractRegex);

        if (nameMatch && contractMatch) {
            const name = nameMatch[1].trim();
            const contractKey = contractMatch[1].trim();
            const pair = { name, contractKey };

            if (!nameContractPairs.some(item => item.contractKey === contractKey)) {
                nameContractPairs.push(pair);
                console.log(`Name: ${name}, Contract: ${contractKey}`);
                sendContractPairsToServer(pair);
            }
        }
    }

    function extractDataFromElements(elements) {
        elements.forEach((element) => {
            if (element.classList && element.classList.contains('text-content') && element.classList.contains('clearfix') && element.classList.contains('with-meta')) {
                extractDataFromElement(element);
            }
            element.querySelectorAll('.text-content.clearfix.with-meta').forEach(subElement => {
                extractDataFromElement(subElement);
            });
        });
    }

    // Initial extraction from existing elements
    const elements = document.querySelectorAll('.text-content.clearfix.with-meta');
    extractDataFromElements(elements);

    // Observe new elements being added to the DOM
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            mutation.addedNodes.forEach((node) => {
                if (node.nodeType === Node.ELEMENT_NODE) {
                    extractDataFromElements([node]);
                }
            });
        });
    });

    observer.observe(document.body, { childList: true, subtree: true });
})();
