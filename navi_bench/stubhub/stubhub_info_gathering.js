(() => {
    const results = [];
    const url = window.location.href;

    /* -----------------------------
     * Utilities
     * ----------------------------- */

    const isVisible = (el) => {
        if (!el) return false;
        const rect = el.getBoundingClientRect();
        const vh = window.innerHeight || document.documentElement.clientHeight;
        const vw = window.innerWidth || document.documentElement.clientWidth;

        return (
            rect.width > 0 &&
            rect.height > 0 &&
            rect.bottom >= 0 &&
            rect.right >= 0 &&
            rect.top <= vh &&
            rect.left <= vw
        );
    };

    const textContent = (el) => {
        return el ? el.textContent?.trim() || null : null;
    };

    const getActiveFilters = () => {
        const params = new URLSearchParams(window.location.search);

        return {
            hasDateFilter: params.has("dates"),
            hasQuantityFilter: params.has("quantity"),
            isEventPage: /\/event\/\d+/.test(url),
        };
    };

    const eventMatchesFilters = (event, filters) => {
        // Event page → only that event
        if (filters.isEventPage) {
            return url.startsWith(event.url);
        }

        // Date filter
        if (filters.hasDateFilter && event.eventDate) {
            if (!url.includes(event.eventDate)) {
                return false;
            }
        }

        return true;
    };

    // NEWNEWNEWN
    const getEventsFromLdJson = () => {
        const scripts = Array.from(
            document.querySelectorAll('script[type="application/ld+json"]')
        );

        const events = [];

        for (const script of scripts) {
            try {
                const data = JSON.parse(script.textContent);

                const graph = data["@graph"] ?? [data];

                for (const item of graph) {
                    if (!item["@type"] || !item["@type"].includes("Event")) continue;

                    events.push({
                        eventName: item.name,
                        eventDate: item.startDate?.split("T")[0],
                        venue: item.location?.name,
                        city: item.location?.address?.addressLocality,
                        url: item.url,
                        domain: item["@type"],
                        availability: item.offers?.availability
                            ? item.offers.availability.includes("InStock")
                                ? "available"
                                : "sold_out"
                            : "unknown",
                        info: "ld+json",
                    });
                }
            } catch {}
        }

        return events;
    };

    const getIndexData = () => {
        const el = document.getElementById("index-data");
        if (!el) return null;

        try {
            return JSON.parse(el.textContent);
        } catch {
            return null;
        }
    };

    /* -----------------------------
    * OpenGraph helpers (StubHub canonical)
    * ----------------------------- */

    const getMeta = (property) => {
        const el = document.querySelector(`meta[property="${property}"]`);
        return el ? el.getAttribute("content") : null;
    };

    const getCanonicalUrl = () => {
        const el = document.querySelector('link[rel="canonical"]');
        return el ? el.getAttribute("href") : null;
    };

    /* -----------------------------
     * Page detection
     * ----------------------------- */

    const isSearchPage = () => {
        return (
            url.includes("/search") ||
            document.querySelector('[data-testid="search-results"]')
        );
    };

    const isEventPage = () => {
        return (
            /\/event\/\d+/.test(url) ||
            document.querySelector('script[type="application/ld+json"]')
        );
    };


    let PAGE_TYPE = "UNKNOWN";
    if (isEventPage()) {
        PAGE_TYPE = "EVENT_PAGE";
    } else if (isSearchPage()) {
        PAGE_TYPE = "SEARCH_PAGE";
    }

    /* -----------------------------
    * Event-level metadata
    * ----------------------------- */

    const getEventName = () => {
        const ogTitle = getMeta("og:title");
        if (ogTitle) {
            return ogTitle.replace(/tickets?/i, "").trim();
        }
        return null;
    };

    const getEventDate = () => {
        const dateEl =
            document.querySelector('[data-testid="event-date"]') ||
            document.querySelector('time');

        if (!dateEl) return null;

        // Prefer machine-readable datetime
        if (dateEl.getAttribute("datetime")) {
            return dateEl.getAttribute("datetime").split("T")[0];
        }

        return null; // parsed later if needed
    };

    const getVenue = () => {
        return (
            textContent(document.querySelector('[data-testid="event-venue"]')) ||
            textContent(document.querySelector('[data-testid="venue-name"]'))
        );
    };

    const getDomain = () => {
        if (url.includes("/sports")) return "sports";
        if (url.includes("/concerts")) return "concerts";
        if (url.includes("/theater")) return "theatre";
        if (url.includes("/festivals")) return "festivals";
        return null;
    };

    /* -----------------------------
    * Sold-out detection
    * ----------------------------- */

    const isEventSoldOut = () => {
        const soldOutTexts = [
            "sold out",
            "no tickets available",
            "this event is sold out",
            "tickets are sold out",
        ];

        const candidates = Array.from(document.querySelectorAll("body *"))
            .filter(isVisible)
            .map(el => el.textContent?.toLowerCase() || "");

        return candidates.some(text =>
            soldOutTexts.some(phrase => text.includes(phrase))
        );
    };

    /* -----------------------------
    * Listing parsers
    * ----------------------------- */

    const parsePriceUSD = (text) => {
        if (!text) return null;
        const match = text.replace(/,/g, "").match(/\$([\d]+(\.\d+)?)/);
        if (!match) return null;
        return parseFloat(match[1]);
    };

    const parseTicketQuantity = (text) => {
        if (!text) return null;
        const match = text.match(/(\d+)\s+(ticket|tickets)/i);
        if (!match) return null;
        return parseInt(match[1], 10);
    };

    const extractTicketListings = (eventMeta) => {
        const listings = [];

        const nodes = Array.from(
            document.querySelectorAll('[data-listing-id]')
        );

        for (const el of nodes) {
            const priceText = Array.from(el.querySelectorAll("div"))
            .map(d => d.textContent?.trim())
            .find(t => /^INR\s?\d/.test(t));

            const price = priceText
            ? parseInt(priceText.replace(/[^\d]/g, ""), 10)
            : null;

            const qtyMatch = el.textContent.match(/(\d+)\s+tickets?/i);
            const ticketQuantity = qtyMatch
            ? parseInt(qtyMatch[1], 10)
            : null;

            if (!price && !ticketQuantity) continue;

            listings.push({
            ...eventMeta,
            availability: "available",
            price,
            ticketQuantity,
            info: "dom-listing",
            });
        }

        return listings;
    };

    const handleEventPage = () => {
        const ldEvents = getEventsFromLdJson();
        if (ldEvents.length === 0) return;

        const filters = getActiveFilters();

        // Decide whether filtering is required
        const shouldFilter =
            filters.isEventPage ||
            filters.hasDateFilter ||
            filters.hasQuantityFilter;

        const candidateEvents = shouldFilter
            ? ldEvents.filter(e => eventMatchesFilters(e, filters))
            : ldEvents;

        // Emit ALL candidates
        for (const event of candidateEvents) {
            // Try listings only on true event pages
            if (filters.isEventPage) {
                const listings = extractTicketListings({
                    eventName: event.eventName,
                    eventDate: event.eventDate,
                    venue: event.venue,
                    domain: event.domain,
                });

                if (listings.length > 0) {
                    results.push(...listings);
                    continue;
                }
            }

            results.push({
                url: event.url || url,
                eventName: event.eventName,
                eventDate: event.eventDate,
                venue: event.venue,
                domain: event.domain,
                availability: event.availability || "unknown",
                info: "ld+json",
            });
        }

    };

    /* -----------------------------
     * Dispatch
     * ----------------------------- */

    if (PAGE_TYPE === "EVENT_PAGE") {
        handleEventPage();
    } else if (PAGE_TYPE === "SEARCH_PAGE") {
        handleSearchPage();
    }

    return results;
  
})();