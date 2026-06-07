/* ==========================================
   ECDICT Explorer Interactions (index.js)
   ========================================== */

document.addEventListener("DOMContentLoaded", () => {
    // 状态管理
    const state = {
        page: 1,
        limit: 20,
        word: "",
        collins: "",
        oxford: "",
        tag: "",
        bnc_min: "",
        bnc_max: "",
        frq_min: "",
        frq_max: "",
        total: 0,
        data: [],
        sort_by: "" // 排序字段：bnc, coca, collins
    };

    // DOM 元素引用
    const searchInput = document.getElementById("search-input");
    const tagContainer = document.getElementById("tag-container");
    const starContainer = document.getElementById("star-container");
    const oxfordToggle = document.getElementById("oxford-toggle");
    
    const bncMinInput = document.getElementById("bnc-min");
    const bncMaxInput = document.getElementById("bnc-max");
    const frqMinInput = document.getElementById("frq-min");
    const frqMaxInput = document.getElementById("frq-max");
    
    const limitSelector = document.getElementById("limit-selector");
    const tableBody = document.getElementById("table-body");
    const totalCountSpan = document.getElementById("total-count");
    
    const loadingSpinner = document.getElementById("loading-spinner");
    const noDataOverlay = document.getElementById("no-data");
    
    const paginationInfo = document.getElementById("pagination-info");
    const paginationControls = document.getElementById("pagination-controls");
    const btnReset = document.getElementById("btn-reset");

    // 抽屉 DOM 引用
    const detailDrawer = document.getElementById("detail-drawer");
    const drawerOverlay = document.getElementById("drawer-overlay");
    const btnCloseDrawer = document.getElementById("btn-close-drawer");
    const drawerWord = document.getElementById("drawer-word");
    const drawerPhonetic = document.getElementById("detail-phonetic");
    const drawerCollins = document.getElementById("detail-collins");
    const drawerOxford = document.getElementById("detail-oxford");
    const drawerTag = document.getElementById("detail-tag");
    const drawerTranslation = document.getElementById("detail-translation");
    const drawerDefinition = document.getElementById("detail-definition");
    const drawerExchange = document.getElementById("detail-exchange");
    const drawerBnc = document.getElementById("detail-bnc");
    const drawerFrq = document.getElementById("detail-frq");

    // 监听实时输入模糊匹配防抖
    let debounceTimer;
    searchInput.addEventListener("input", (e) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            state.word = e.target.value.trim();
            state.page = 1;
            fetchWords();
        }, 300);
    });

    // 标签单选/多选控制
    tagContainer.addEventListener("click", (e) => {
        const chip = e.target.closest(".chip");
        if (!chip) return;
        
        const wasActive = chip.classList.contains("active");
        
        // 清理其他标签的 active，实现单选。如果需要多选，可以去除这行
        tagContainer.querySelectorAll(".chip").forEach(c => c.classList.remove("active"));
        
        if (!wasActive) {
            chip.classList.add("active");
            state.tag = chip.dataset.tag;
        } else {
            state.tag = "";
        }
        state.page = 1;
        fetchWords();
    });

    // 星级单选控制
    starContainer.addEventListener("click", (e) => {
        const starBtn = e.target.closest(".star-btn");
        if (!starBtn) return;
        
        const wasActive = starBtn.classList.contains("active");
        starContainer.querySelectorAll(".star-btn").forEach(s => s.classList.remove("active"));
        
        if (!wasActive) {
            starBtn.classList.add("active");
            state.collins = starBtn.dataset.star;
        } else {
            // 如果取消了选择，或者点击了原本就是 active 的按钮，都默认高亮“全部”按钮
            const allBtn = starContainer.querySelector('[data-star=""]');
            if (allBtn) allBtn.classList.add("active");
            state.collins = "";
        }
        state.page = 1;
        fetchWords();
    });

    // 牛津 Toggle 监听
    oxfordToggle.addEventListener("change", (e) => {
        state.oxford = e.target.checked ? "1" : "";
        state.page = 1;
        fetchWords();
    });

    // 语料库数值区间筛选防抖
    const registerRangeListener = (element, field) => {
        element.addEventListener("input", (e) => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                state[field] = e.target.value.trim();
                state.page = 1;
                fetchWords();
            }, 500);
        });
    };
    registerRangeListener(bncMinInput, "bnc_min");
    registerRangeListener(bncMaxInput, "bnc_max");
    registerRangeListener(frqMinInput, "frq_min");
    registerRangeListener(frqMaxInput, "frq_max");

    // 每页条数切换
    limitSelector.addEventListener("change", (e) => {
        state.limit = parseInt(e.target.value);
        state.page = 1;
        fetchWords();
    });

    // 表头可排序元素声明
    const sortableHeaders = {
        "bnc": document.getElementById("th-bnc"),
        "coca": document.getElementById("th-coca"),
        "collins": document.getElementById("th-collins")
    };

    // 重置全部筛选条件
    btnReset.addEventListener("click", () => {
        searchInput.value = "";
        bncMinInput.value = "";
        bncMaxInput.value = "";
        frqMinInput.value = "";
        frqMaxInput.value = "";
        oxfordToggle.checked = false;
        
        tagContainer.querySelectorAll(".chip").forEach(c => c.classList.remove("active"));
        starContainer.querySelectorAll(".star-btn").forEach(s => s.classList.remove("active"));
        const allBtn = starContainer.querySelector('[data-star=""]');
        if (allBtn) allBtn.classList.add("active");

        state.page = 1;
        state.word = "";
        state.collins = "";
        state.oxford = "";
        state.tag = "";
        state.bnc_min = "";
        state.bnc_max = "";
        state.frq_min = "";
        state.frq_max = "";
        state.sort_by = ""; // 重置排序状态
        
        // 移除表头高亮样式
        Object.values(sortableHeaders).forEach(el => {
            if (el) el.classList.remove("sorted-desc", "sorted-asc");
        });
        
        fetchWords();
    });

    // 导出 CSV 功能
    const btnExport = document.getElementById("btn-export");
    btnExport.addEventListener("click", () => {
        const params = new URLSearchParams();
        if (state.word) params.append("word", state.word);
        if (state.collins) params.append("collins", state.collins);
        if (state.oxford) params.append("oxford", state.oxford);
        if (state.tag) params.append("tag", state.tag);
        if (state.bnc_min) params.append("bnc_min", state.bnc_min);
        if (state.bnc_max) params.append("bnc_max", state.bnc_max);
        if (state.frq_min) params.append("frq_min", state.frq_min);
        if (state.frq_max) params.append("frq_max", state.frq_max);
        if (state.sort_by) params.append("sort_by", state.sort_by);

        // 动态构建链接进行下载
        const downloadUrl = `/api/words/export?${params.toString()}`;
        const a = document.createElement("a");
        a.href = downloadUrl;
        a.download = "ecdict_export.csv";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    });

    // 关闭单词详情抽屉
    const closeDrawer = () => {
        detailDrawer.classList.remove("open");
    };
    btnCloseDrawer.addEventListener("click", closeDrawer);
    drawerOverlay.addEventListener("click", closeDrawer);

    // 获取并渲染数据
    async function fetchWords() {
        showLoading(true);
        noDataOverlay.classList.add("hidden");
        
        // 构建请求 query 字符串
        const params = new URLSearchParams();
        params.append("page", state.page);
        params.append("limit", state.limit);
        if (state.word) params.append("word", state.word);
        if (state.collins) params.append("collins", state.collins);
        if (state.oxford) params.append("oxford", state.oxford);
        if (state.tag) params.append("tag", state.tag);
        if (state.bnc_min) params.append("bnc_min", state.bnc_min);
        if (state.bnc_max) params.append("bnc_max", state.bnc_max);
        if (state.frq_min) params.append("frq_min", state.frq_min);
        if (state.frq_max) params.append("frq_max", state.frq_max);
        if (state.sort_by) params.append("sort_by", state.sort_by);

        try {
            const response = await fetch(`/api/words?${params.toString()}`);
            const result = await response.json();
            
            if (result.success) {
                state.total = result.total;
                state.data = result.data;
                renderTable();
                renderPagination();
            }
        } catch (error) {
            console.error("加载单词失败: ", error);
        } finally {
            showLoading(false);
        }
    }

    function showLoading(isLoading) {
        if (isLoading) {
            loadingSpinner.classList.remove("hidden");
        } else {
            loadingSpinner.classList.add("hidden");
        }
    }

    // 格式化展示中文翻译中的换行
    function formatTranslation(text) {
        if (!text) return "--";
        // 替换字面量 \n 字符和真实换行
        return text.replace(/\\n/g, "<br>").replace(/\n/g, "<br>");
    }

    // 渲染表格
    function renderTable() {
        tableBody.innerHTML = "";
        totalCountSpan.textContent = state.total.toLocaleString();

        if (state.data.length === 0) {
            noDataOverlay.classList.remove("hidden");
            return;
        }

        state.data.forEach(item => {
            const tr = document.createElement("tr");
            tr.dataset.id = item.id;
            
            // 处理 Tag 药丸格式
            let tagHTML = "";
            if (item.tag) {
                tagHTML = item.tag.split(" ").map(t => `<span class="tag-pill">${t}</span>`).join("");
            }
            
            // 柯林斯显示星星
            const stars = item.collins > 0 ? `${item.collins}★` : "";
            
            // 牛津标记
            const oxfordSign = item.oxford === 1 ? '<span class="oxf-tag">✓</span>' : "--";

            tr.innerHTML = `
                <td class="word-cell">${item.word}</td>
                <td class="ipa">${item.phonetic || "--"}</td>
                <td><div class="translation-cell" title="${item.translation}">${formatTranslation(item.translation)}</div></td>
                <td>${item.pos || "--"}</td>
                <td class="col-star">${stars}</td>
                <td style="text-align:center">${oxfordSign}</td>
                <td>${tagHTML || "--"}</td>
                <td>${item.bnc ? item.bnc.toLocaleString() : "--"}</td>
                <td>${item.frq ? item.frq.toLocaleString() : "--"}</td>
                <td><small style="color:var(--text-muted)">${item.exchange ? item.exchange.replace(/\//g, ", ") : "--"}</small></td>
            `;
            
            // 行点击事件展示侧边详情抽屉
            tr.addEventListener("click", () => showDetail(item));
            tableBody.appendChild(tr);
        });
    }

    // 侧边抽屉展示单词详细数据
    function showDetail(item) {
        drawerWord.textContent = item.word;
        drawerPhonetic.textContent = item.phonetic ? `${item.phonetic}` : "--";
        drawerCollins.textContent = item.collins > 0 ? "★".repeat(item.collins) + ` (${item.collins} 星)` : "未评级";
        drawerOxford.textContent = item.oxford === 1 ? "✓ 是" : "否";
        drawerTag.textContent = item.tag ? item.tag.split(" ").join(", ") : "--";
        
        drawerTranslation.innerHTML = formatTranslation(item.translation);
        drawerDefinition.textContent = item.definition || "暂无英文双解释义";
        drawerExchange.textContent = item.exchange ? item.exchange.replace(/\//g, " | ") : "无派生及变化形式";
        
        drawerBnc.textContent = item.bnc ? item.bnc.toLocaleString() : "--";
        drawerFrq.textContent = item.frq ? item.frq.toLocaleString() : "--";
        
        detailDrawer.classList.add("open");
    }

    // 渲染分页组件
    function renderPagination() {
        paginationControls.innerHTML = "";
        const totalPages = Math.ceil(state.total / state.limit);
        
        if (totalPages <= 1) {
            paginationInfo.textContent = `共 ${state.total} 条数据`;
            return;
        }

        const startIdx = (state.page - 1) * state.limit + 1;
        const endIdx = Math.min(state.page * state.limit, state.total);
        paginationInfo.textContent = `当前显示 ${startIdx.toLocaleString()} - ${endIdx.toLocaleString()} 条，共 ${state.total.toLocaleString()} 条`;

        // 辅助创建分页按钮
        const createBtn = (pageNumber, text, classes = []) => {
            const btn = document.createElement("div");
            btn.className = `page-btn ${classes.join(" ")}`;
            btn.textContent = text;
            if (!classes.includes("disabled") && !classes.includes("active")) {
                btn.addEventListener("click", () => {
                    state.page = pageNumber;
                    fetchWords();
                });
            }
            return btn;
        };

        // 1. 上一页
        paginationControls.appendChild(createBtn(state.page - 1, "◀", state.page === 1 ? ["disabled"] : []));

        // 2. 页码展示逻辑（支持大页数折叠）
        const range = 2; // 当前页左右显示的页码范围
        let pages = [];

        for (let i = 1; i <= totalPages; i++) {
            if (i === 1 || i === totalPages || (i >= state.page - range && i <= state.page + range)) {
                pages.push(i);
            } else if (pages[pages.length - 1] !== "...") {
                pages.push("...");
            }
        }

        pages.forEach(p => {
            if (p === "...") {
                const dot = document.createElement("div");
                dot.className = "page-btn disabled";
                dot.textContent = "...";
                paginationControls.appendChild(dot);
            } else {
                paginationControls.appendChild(createBtn(p, p, state.page === p ? ["active"] : []));
            }
        });

        // 3. 下一页
        paginationControls.appendChild(createBtn(state.page + 1, "▶", state.page === totalPages ? ["disabled"] : []));
    }

    // 绑定表头点击事件以支持字段倒序排序
    Object.entries(sortableHeaders).forEach(([field, thEl]) => {
        if (!thEl) return;
        thEl.addEventListener("click", () => {
            if (state.sort_by === field) {
                state.sort_by = ""; // 再次点击取消排序
            } else {
                state.sort_by = field;
            }
            
            // 刷新表头高亮样式
            Object.entries(sortableHeaders).forEach(([f, el]) => {
                if (el) {
                    el.classList.remove("sorted-desc", "sorted-asc");
                    if (f === state.sort_by) {
                        if (f === "bnc" || f === "coca") {
                            el.classList.add("sorted-asc");
                        } else {
                            el.classList.add("sorted-desc");
                        }
                    }
                }
            });
            
            state.page = 1;
            fetchWords();
        });
    });

    // 首次初始化加载数据
    fetchWords();
});
