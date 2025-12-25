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

    
    const getEventMetaFromHeader = () => {
        const header = document.querySelector('[data-testid="event-detail-header"]');
        if (!header) return null;

        // Event name
        const nameEl = header.querySelector("h6");
        const eventName = nameEl?.textContent?.trim() || null;

        // Date text (human readable → evaluator-safe string)
        const dateText = Array.from(header.querySelectorAll("span"))
            .map(s => s.textContent?.trim())
            .find(t => /\d{4}/.test(t)) || null;

        // Venue (button text)
        const venueBtn = header.querySelector("button");
        const venue = venueBtn?.textContent?.trim() || null;

        // Infer city from event name suffix
        let city = null;
        if (eventName && eventName.includes(" - ")) {
            city = eventName.split(" - ").pop().trim();
        }

        return {
            eventName,
            eventDate: dateText,   // keep human-readable for now
            venue,
            city,
            url: window.location.href,
        };
    };

    /* -----------------------------
    * Filters
    * ----------------------------- */
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

    /* -----------------------------
    * Page detection
    * ----------------------------- */
    // const isSearchPage = () => {
    //     return (
    //         url.includes("/search") ||
    //         document.querySelector('[data-testid="search-results"]')
    //     );
    // };

    const isSearchPage = () => {
        return (
            document.querySelector('script[type="application/ld+json"]')
        );
    };

    const isEventPage = () => {
        return /\/event\/\d+/.test(window.location.href);
    };

    const isListingsPage = () => {
        return (
            /\/event\/\d+/.test(window.location.href) &&
            document.querySelector('[data-testid="listings-container"]')
        );
    };


    let PAGE_TYPE = "UNKNOWN";
    if (isListingsPage()) {
        PAGE_TYPE = "LISTINGS_PAGE";
    } else if (isEventPage()) {
        PAGE_TYPE = "EVENT_PAGE";
    } else if (isSearchPage()) {
        PAGE_TYPE = "SEARCH_PAGE";
    }


    /* -----------------------------
    * LD+JSON extraction
    * ----------------------------- */
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


    /* -----------------------------
    * Event-level metadata
    * ----------------------------- */

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
    * Listing parsers
    * ----------------------------- */

    const extractTicketListings = (eventMeta) => {
        const listings = [];

        const cards = document.querySelectorAll('[data-listing-id]');

        for (const card of cards) {
            const rawPrice = card.getAttribute('data-price');
            const isSold = card.getAttribute('data-is-sold') === "1";

            const price = rawPrice
                ? parseInt(rawPrice.replace(/[^\d]/g, ""), 10)
                : null;

            const qtyMatch = card.textContent.match(/(\d+)\s+tickets?/i);
            const ticketQuantity = qtyMatch
                ? parseInt(qtyMatch[1], 10)
                : null;

            if (!price) continue;

            listings.push({
                ...eventMeta,
                availability: isSold ? "sold_out" : "available",
                price,
                ticketQuantity,
                info: "dom-listing",
            });
        }

        return listings;
    };


    const handleSearchPage = () => {
        const ldEvents = getEventsFromLdJson();
        // if (ldEvents.length === 0) return;

        const filters = getActiveFilters();

        // Decide whether filtering is required
        const shouldFilter =
            filters.isEventPage ||
            filters.hasDateFilter ||
            filters.hasQuantityFilter;

        const candidateEvents = shouldFilter
            ? ldEvents.filter(e => eventMatchesFilters(e, filters))
            : ldEvents;

        /* EVENT / SEARCH PAGE — emit event-level info */
        for (const event of candidateEvents) {
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
    }

    /* =============================
    * 1️⃣ LISTINGS PAGE (DOM ONLY)
    * ============================= */
    const handleListingsPage = () => {
        const container = document.querySelector('[data-testid="listings-container"]');
        if (!container) return; // React not ready

        const eventMeta = getEventMetaFromHeader();
        if (!eventMeta) return;

        const listings = extractTicketListings({
            eventName: eventMeta.eventName,
            eventDate: eventMeta.eventDate,
            venue: eventMeta.venue,
        });

        if (listings.length > 0) {
            results.push(...listings);
        }
    };

    /* -----------------------------
     * Dispatch
     * ----------------------------- */

    if (PAGE_TYPE === "LISTINGS_PAGE") {
        handleListingsPage();
    } else if (PAGE_TYPE === "SEARCH_PAGE") {
        handleSearchPage();
    }

    return results;
  
})();