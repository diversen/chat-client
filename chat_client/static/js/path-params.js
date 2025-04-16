// Write a function that getURLParts(url) that takes a single argument numPath 
// (integer). The function should return the nth part of the URL path. If the
// URL path is less than n parts, return null.

function getURLPart(numPath) {


    let url = window.location.href;
    url = processUrl(url);

    
    let urlParts = url.split('/');
    if (urlParts.length < numPath) {
        return null;
    }
    return urlParts[numPath];
}

function processUrl(url) {
    // Remove the protocol part (http:// or https://)
    const withoutProtocol = url.replace(/^https?:\/\//i, '');

    // Extract the domain name and remove it
    const withoutDomain = withoutProtocol.split('/')[1];

    // Remove hash part if exists
    let withoutHash = withoutDomain;
    if (withoutDomain.includes('#')) {
        withoutHash = withoutDomain.split('#')[0];
    }

    // Remove query parameters if exist
    let finalPath = withoutHash;
    if (withoutHash.includes('?')) {
        finalPath = withoutHash.split('?')[0];
    }

    return finalPath;
}


export { getURLPart };


