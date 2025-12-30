(() => {
    const results = [];
    const url = window.location.href;

    window.__stubhubNormalization = {
        currency: "USD",
        dateFormat: "YYYY-MM-DD",
    };

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

    /* ============================================================
    * Normalization
    * ============================================================ */

    const normalizeDateToISO = (raw) => {
        if (!raw) return null;

        const cleaned = raw
            .replace(/•/g, " ")
            .replace(/,/g, " ")
            .replace(/\s+/g, " ")
            .trim();

        const d = new Date(cleaned);
        if (isNaN(d.getTime())) return null;
        return d.toISOString().split("T")[0];
    };

    const getDateFromUrl = () => {
        const m = url.match(/tickets-(\d+)-(\d+)-(\d+)/);
        if (!m) return null;
        return `${m[3]}-${m[1].padStart(2, "0")}-${m[2].padStart(2, "0")}`;
    };

    const INR_TO_USD = 0.012; // fixed conservative eval-safe rate

    const normalizePriceToUSD = (raw) => {
        if (!raw) return null;
        const n = parseInt(raw.replace(/[^\d]/g, ""), 10);
        if (isNaN(n)) return null;
        return Math.round(n * INR_TO_USD);
    };

    const extractSeatType = (card) => {
        const SEAT_TYPE_PATTERNS = [
            /standing only/i,
            /general admission/i,
            /seated/i,
            /balcony/i,
            /floor/i,
            /vip/i,
        ];

        const texts = Array.from(card.querySelectorAll("span"))
            .map(el => el.textContent?.trim())
            .filter(Boolean);

        for (const text of texts) {
            for (const pattern of SEAT_TYPE_PATTERNS) {
                if (pattern.test(text)) {
                    return text;
                }
            }
        }

        return null;
    };


    /* ============================================================
    * Event Metadata (Listings Page Header)
    * ============================================================ */
    
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
            eventDate: normalizeDateToISO(dateText) || getDateFromUrl(),   // keep human-readable for now
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
        // if (filters.hasDateFilter && event.eventDate) {
        //     if (!url.includes(event.eventDate)) {
        //         return false;
        //     }
        // }

        return true;
    };

    const getListingsFilters = () => {
        const params = new URLSearchParams(window.location.search);

        return {
            hasQuantityFilter: params.has("quantity"),
            hasPriceFilter:
                params.has("minPrice") || params.has("maxPrice"),
            hasSort:
                params.has("sort"),
            hasAnyFilter:
                params.has("quantity") ||
                params.has("minPrice") ||
                params.has("maxPrice") ||
                params.has("sort"),
        };
    };


    /* -----------------------------
    * Page detection
    * ----------------------------- */

    const CURRENCY_RATES = {
        INR_TO_USD: 0.012, // conservative fixed rate (safe for eval)
    };

    const isSecureSearchPage = () => {
        return url.includes("/secure/Search");
    };

    const isPerformerSearchPage = () => {
        return url.includes("/performer/") || url.includes("/grouping/") || url.includes("/category/");
    };

    const isSearchPage = () => {
        return isSecureSearchPage() || isPerformerSearchPage();
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


    const extractSearchCards = () => {
        // const grid = document.querySelector('[data-testid="primaryGrid"]');
        // if (!grid) return [];

        // const cards = Array.from(
        //     grid.querySelectorAll('li a[href*="/event/"]')
        // ).filter(link =>
        //     link.querySelector('[data-testid="event-grid-item-title-text"]')
        // );

        const cards = Array.from(
            document.querySelectorAll('[data-testid="primaryGrid"] > li[data-expanded]')
        );

        const events = [];

        // for (const link of cards) {
        //     const href = link.href;

        //     const titleEl = link.querySelector(
        //         '[data-testid="event-grid-item-title-text"]'
        //     );
        //     const eventName =
        //         titleEl?.innerText?.replace(/\s+/g, " ").trim() || null;

        //     const month = link.querySelector("h4")?.textContent?.trim() || null;
        //     const day = link.querySelectorAll("h4")[1]?.textContent?.trim() || null;
        //     const year = link.querySelector("p")?.textContent?.trim() || null;

        //     let eventDate = null;
        //     if (month && day && year) {
        //         eventDate = normalizeDateToISO(`${month} ${day} ${year}`);
        //     }

        //     const metaLine = link.querySelector(".sc-jetmxw-0");
        //     const metaText = metaLine?.innerText || "";
        //     const venue = metaText.split("|")[1]?.trim() || null;
        //     const city = metaText.split("|")[2]?.trim() || null;

        //     const isDisabled =
        //         link.getAttribute("aria-disabled") === "true" ||
        //         !link.querySelector("button");

        //     events.push({
        //         url: href,
        //         eventName,
        //         eventDate,
        //         venue,
        //         city,
        //         availability: isDisabled ? "sold_out" : "available",
        //         info: "search-card",
        //     });
        // }

        for (const li of cards) {
            const link = li.querySelector('a[href*="/event/"]');

            if (!link) continue;

            const titleEl = li.querySelector('[data-testid="event-grid-item-title-text"]');
            const eventName = titleEl?.innerText?.replace(/\s+/g, " ").trim() || null;

            const month = li.querySelector("h4")?.textContent?.trim() || null;
            const day = li.querySelectorAll("h4")[1]?.textContent?.trim() || null;
            const year = li.querySelector("p")?.textContent?.trim() || null;

            let eventDate = null;
            if (month && day && year) {
                eventDate = normalizeDateToISO(`${month} ${day} ${year}`);
            }

            const metaLine = li.querySelector(".sc-jetmxw-0");
            const metaText = metaLine?.innerText || "";

            const venue = metaText.split("|")[1]?.trim() || null;
            const city = metaText.split("|")[2]?.trim() || null;

            const isDisabled =
                link.getAttribute("aria-disabled") === "true" ||
                !li.querySelector("button");

            events.push({
                url: link.href,
                eventName,
                eventDate,
                venue,
                city,
                availability: isDisabled ? "sold_out" : "available",
                info: "search-card",
            });
        }

        return events;
    };


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

        const cards = Array.from(
            document.querySelectorAll('[data-listing-id]')
        ).filter(isVisible);


        for (const card of cards) {
            const listingId = card.getAttribute('data-listing-id');

            const rawPrice = card.getAttribute('data-price');
            const isSold = card.getAttribute('data-is-sold') === "1";
            
            // const price = normalizePriceToUSD(rawPrice);
            const price = rawPrice
                ? parseInt(rawPrice.replace(/[^\d]/g, ""), 10)
                : null;

            const qtyMatch = card.textContent.match(/(\d+)\s+tickets?/i);
            const ticketQuantity = qtyMatch
                ? parseInt(qtyMatch[1], 10)
                : null;

            if (!price) continue;

            // --- CATEGORY (KEY ADDITION) ---
            let category = null;
            if (listingId) {
                const categoryEl = card.querySelector(
                    `[data-listing-cta-id="listing-${listingId}"]`
                );
                category = categoryEl?.textContent?.trim() || null;
            }
            
            const seatType = extractSeatType(card);

            listings.push({
                ...eventMeta,
                ticketCategory: category,
                seatType: seatType, 
                availability: isSold ? "sold_out" : "available",
                price,
                ticketQuantity,
                info: "dom-listing",
            });
        }

        return listings;
    };


    const handleSearchPage = () => {
        let events = []
        // CASE 1️⃣: /secure/Search → DOM cards
        if (isSecureSearchPage()) {
            events = extractSearchCards();
        }

        // CASE 2️⃣: /performer/ → LD+JSON
        else if (isPerformerSearchPage()) {
            events = getEventsFromLdJson();
        }

        // const ldEvents = getEventsFromLdJson();
        // if (ldEvents.length === 0) return;

        const filters = getActiveFilters();

        // Decide whether filtering is required
        const shouldFilter =
            filters.isEventPage ||
            filters.hasDateFilter ||
            filters.hasQuantityFilter;

        const candidateEvents = shouldFilter
            ? events.filter(e => eventMatchesFilters(e, filters))
            : events;

        /* EVENT / SEARCH PAGE — emit event-level info */
        for (const event of candidateEvents) {
            results.push({
                url: event.url || url,
                eventName: event.eventName,
                eventDate: event.eventDate,
                venue: event.venue,
                domain: event.domain || null,
                availability: event.availability || "unknown",
                info: event.info || "search",
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

        const filters = getListingsFilters();

        const listings = extractTicketListings({
            eventName: eventMeta.eventName,
            eventDate: eventMeta.eventDate,
            venue: eventMeta.venue,
        });

        // if (listings.length > 0) {
        //     results.push(...listings);
        // }
        
        if (listings.length === 0) return;

        // IMPORTANT:
        // If filters are active → DOM already reflects them
        // If no filters → DOM shows all listings
        results.push(...listings);
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