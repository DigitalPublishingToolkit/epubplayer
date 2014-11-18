// alert(location.search);
(function () {

var PAGE_WIDTH = 105,
    PAGE_HEIGHT = 148,
    hide_toc_timeout_id = null,
    data = null,
    player = d3.select("#player"),
    viewframe = player
        .append("div")
        .attr("class", "iframe")
        .append("iframe")
        .attr("id", "viewframe")
        .attr("name", "viewframe"),
    pagesdiv = player
        .append("div")
        .attr("class", "pages"),
    librarydiv = player
        .append("div")
        .attr("class", "library"),
    librarydivcontents = librarydiv
        .append("div")
        .attr("class", "contents"),
    bookmarkcorner = player
        .append("div")
        .attr("class", "bookmark")
        .on("mouseover", add_mouseover_class)
        .on("mouseout", remove_mouseover_class)
        .on("click", bookmark_click),
    books,
    pages,
    currentBook = null,
    currentPage,
    bookmarksbook;

function cancelable (fn, delay) {
    var timeout_id = null;
    function ret () {
        var that = this,
            args = Array.prototype.slice.call(arguments);
        if (timeout_id == null) {
            timeout_id = window.setTimeout(function () {
                fn.apply(that, args);
                timeout_id = null;
            }, delay || default_delay);
        }
    }
    ret.cancel = function () {
        if (timeout_id !== null) {
            window.clearTimeout(timeout_id);
            timeout_id = null;
        }
        return ret;
    }
    ret.delay = function (d) {
        if (arguments.length == 0) {
            return delay;         
        }
        delay = d;
        return ret;
    }
    return ret;
}

var hide_pages = cancelable(function () {
            // console.log("hiding");
            hide(pagesdiv);
        }).delay(1000),
    hide_library = cancelable(function () {
        hide(librarydiv);
    }).delay(1000);

function toggle (elt) {
    elt.style("display", elt.style("display") == "block" ? "none" : "block");
}

function show (elt) {
    if (elt.style("display") !== "block") {
        elt.style("display", "block");
    }
}

function hide (elt) {
    if (elt.style("display") !== "none") {
        elt.style("display", "none");
    }
}

/* pagestrigger */
player
    .append("div")
    .attr("class", "pagestrigger")
    .append("div")
    .attr("class", "trigger")
    .on("click", function () {
        console.log("pagestrigger");
        toggle(pagesdiv);
    })
    .on("mouseover", function () {
        d3.select(this).classed("mouseover", true);
        show(pagesdiv);
        hide_pages.cancel();
    })
    .on("mouseout", function () {
        d3.select(this).classed("mouseover", false);
    });

/* prev & next page buttons */

function add_mouseover_class () { d3.select(this).classed("mouseover", true); }
function remove_mouseover_class () { d3.select(this).classed("mouseover", false); }

player
    .append("div")
    .attr("class", "prevpage")
    .append("div")
    .attr("class", "trigger")
    .on("mouseover", add_mouseover_class)
    .on("mouseout", remove_mouseover_class)
    .on("click", prev_page);

player
    .append("div")
    .attr("class", "nextpage")
    .append("div")
    .attr("class", "trigger")
    .on("mouseover", add_mouseover_class)
    .on("mouseout", remove_mouseover_class)
    .on("click", next_page);


/* library */

player
    .append("div")
    .attr("class", "librarytrigger")
    .append("div")
    .attr("class", "trigger")
    .on("mouseover", function () {
        add_mouseover_class.call(this);
        hide_library.cancel();
        show_library();
    })
    .on("mouseout", remove_mouseover_class)
    .on("click", toggle_library);

function toggle_library () {
    toggle(librarydiv);
}

function show_library () {
    show(librarydiv);
}

librarydiv.on("mouseover", function () {
    hide_library.cancel();
}).on("mouseout", function () {
    hide_library();
});

/*
viewframe.on("load", function () {
    console.log("viewframe.load");
    var url = $(this).attr("src");
    update_active_page();
    if (toc.style("display") == "block") {
        hide_toc_timeout_id = window.setTimeout(function () {
            toc.style("display", "none");
            hide_toc_timeout_id = null;
        }, 2000);
    }
});
*/

function urlparse (href) {
    var ret = {
            query: {},
            fragment: ''
        },
        m = href.match(/^(.*)\#([^#]*)$/),
        pair;
    if (m && m.length) {
        ret.fragment = m[2];
        href = m[1];
    };
    m = href.match(/\?(.*)$/);
    if (m && m.length) {
        m = m[1].split("&");
        for (var i=0, l=m.length; i<l; i++) {
            pair = m[i].split("=", 2);
            ret.query[pair[0]] = pair[1];
        }
    }
    return ret;
}

function update_bookmark () {
    // console.log("update_bookmark", currentPage, currentPage.bookmarked);
    bookmarkcorner.classed("folded", currentPage && currentPage.bookmarked == true);
}

function set_page (page) {
    var src;
    if (typeof(page) == "string") {
        src = page;
    } else {
        currentPage = page;
        src = page.link;
        update_bookmark();
    }
    // console.log("set_page", src);
    viewframe.attr("src", src);
    update_active_page();
}

function update_active_page () {
    var src = viewframe.attr("src");
    var href = viewframe[0][0].contentWindow.location.href,
        m = href.match(/https?:\/\/.*?\/(.*)$/);
    if (m !== null) { href = m[1]; }
    pages.classed("active", function (d) {
        // console.log("?", d.link, href, src);
        return (d.link == src);
        // return (d.link == href);
    });
}

function prev_page () {
    d3.select("div.page.active").each(function (d) {
        if ((d.index - 1) >= 0) {
            set_page(currentBook.pages[d.index-1]);
        }
    })
    show(pagesdiv);
    hide_pages();
}

function next_page() {
    var page;
    // pick the last active page (when multiple)
    d3.selectAll("div.page.active").each(function (d) { page = d; })
    if (page && (page.index + 1) < page.book.pages.length) {
        set_page(currentBook.pages[page.index+1]);
    }
    show(pagesdiv);
    hide_pages();
}

function tweak_data (data) {
    // Augment the data to include a flattend pages list &
    // page.index'es that goes [0-1) ie array.index/array.length
    bookmarksbook = {
        path: "",
        toc: [],
        annotated_spine: [{'link': '/epub_bookmarks.html', 'label': 'Bookmarks'}],
        title: "Bookmarks"
    };
    data.books.push(bookmarksbook);
 
    data.books.forEach(function (book) {
        // book.pages = flatten_toc(book.toc);
        book.pages = book.annotated_spine;
        var numpages = book.pages.length;
        // set page index, findex, book
        book.pages.forEach(function (page, i) {
            page.label = (i == 0) ?     book.title : page.label;
            page.index = i;
            page.findex = i/(numpages-1);
            page.book = book;
            // console.log(page.label, page.index);
        });
    });
}

function init_library (data) {
    var books = librarydivcontents
            .selectAll("div.bookcover")
            .data(data.books);
    var enter = books.enter()
            .append("div")
            .attr("class", "bookcover")
            .on("click", function (d) {
                if (d3.event.target.tagName == "A") return;
                if (d !== currentBook) {
                    openBook(d);
                    set_page(d.pages[0]);
                    show(pagesdiv);
                }
            });
    enter.append("span")
        .attr("class", "title")
        .text(function (d) { return d.title });
    enter.append("div")
        .attr("class", "links")
        .append("a")
        .text("download")
        .attr("class", "download")
        .attr("target", "_download")
        .attr("download", function (d) {
            return d.path
        })
        .attr("href", function (d) {
            if (d !== bookmarksbook) {
                return "/"+d.path;
            }
        })
        .on("click", function (d) {
            if (d === bookmarksbook) {
                d3.event.preventDefault();
                alert("THIS FEATURE IS COMING SOON!\n"+d.pages
                        .filter(function (d) { return d.src !== undefined; })
                        .map(function (d) { return d.book.path + "?href=" + d.src })
                        .join("\n"));
            }
        });
    // add cover if present        
    enter.filter(function (d) {
        return (d.cover);    
    })
    .each(function (d) {
        var t = d3.select(this);
        t.select("span.title").remove();
    })
    .append("img")
    .classed("cover", true)
    .attr("src", function (d) { return d.cover; });
}

function pageZ (d) { return 1000 - d.index };
function page_click (d) {
    // console.log("page_click", d);
    d3.event.preventDefault();
    set_page(d);
}

function bookmark_click () {
    if (currentPage) {
        currentPage.bookmarked = !(currentPage.bookmarked == true);
        if (currentPage.bookmarked) {
            var i = bookmarksbook.pages.indexOf(currentPage);
            if (i == -1) {
                bookmarksbook.pages.push(currentPage);
            }
        } else {
            bookmarksbook.remove(currentPage);
        }
        update_bookmark();
    }
}

function openBook (book) {
    // update pages
    // console.log("openBook", book);
    currentBook = book;
    if (!book) return;
    var max_dx = 80,
        max_dy = 60,
        ww = window.innerWidth,
        wh = window.innerHeight,
        total_x = ww - PAGE_WIDTH - 20,
        total_y = wh - PAGE_HEIGHT - 20,
        numpages = book.pages.length;

    if (numpages > 1) {
        dx = total_x / (numpages - 1);
        dx = Math.min(max_dx, dx);
        total_x = dx * (numpages - 1);
    }
    if (numpages > 1) {
        dy = total_y / (numpages - 1);
        dy = Math.min(max_dy, dy);
        total_y = dy * (numpages - 1);
    }

    // set/update findex/index in pages
    book.pages.forEach(function (d, i) {
        // console.log("*", d, i);
        d.index = i;
        d.findex = (numpages > 1) ? (i/(numpages-1)) : 0;
    });

    pages = pagesdiv.selectAll("div.page")
            .data(book.pages, function (d) { return d.link+"/"+d.label+"/"+d.depth });
        xscale = d3.scale.linear()
            .range([20, total_x]),
        yscale = d3.scale.linear()
            .range([20, total_y]);

    // ENTER
    var enter = pages.enter()
        .append("div")
        .attr("class", "page")
        .style("z-index", pageZ)
        .on("click", page_click)
        .on("mousemove", update_page_from_mouse)
        .on("mouseover", function (d) {
            d3.select(this).classed("mouseover", true);
            hide_pages.cancel();
        })
        .on("mouseout", function (d) {
            pages.classed("mouseover", false);
            hide_pages();
        });

    enter.append("a")
        .text(function (d) { return d.label })
        .attr("href", function (d) { return d.link })
        .attr("target", "viewframe")
        .on("click", page_click);

    // cover pages
    enter.filter(function (d) { return ((d.index == 0) && d.book.cover); })
        .classed("cover", true)
        .append("img")
        .classed("cover", true)
        .attr("src", function (d) { return d.book.cover; });

    pages.exit().remove();

    // layout
    pages
        .style("left", function (d, x) { return xscale(d.findex)+"px"; })
        .style("top", function (d, x) { return yscale(d.findex)+"px"; });
    
    //var currentBookData = d3.select(currentBook).datum(),
    //    currentPages = d3.select(currentBook).selectAll("div.page"),
    //   numpages = currentPages[0].length;

    function update_page_from_mouse () {
        var x = d3.event.clientX - (PAGE_WIDTH/2),
            y = d3.event.clientY - (PAGE_HEIGHT/2);
        var index = Math.floor(xscale.invert(x) * numpages);
        // set page from index
        // console.log("index", index, numpages);
        if (index >= 0 && index < numpages) {
            pages.classed("mouseover", function (d) {
                return (d.index == index);
            });
        }
    }
}

d3.select(window).on("resize", function () {
    openBook(currentBook);
});

// Load the data
d3.json(location.search+"&c=json", function (book_data) {
    // console.log("loaded data", book_data);    
    data = book_data;
    tweak_data(data);
    init_library(book_data);
    // return;
    // openBook(d3.select("div.book")[0][0]);
    openBook(data.books[0]);
    set_page(data.books[0].pages[0]);
    // console.log("flat", flatten_toc(data.books[0].toc));
})

})(window);



/*
function flatten_toc (toc) {
    var ret = [];
    function _xpand(list) {
        for (var i=0, l=list.length; i<l; i++) {
            ret.push(list[i]);
            if (list[i].children && list[i].children.length) {
                _xpand(list[i].children);
            }
        }
    }
    _xpand(toc);
    return ret;
}
*/

