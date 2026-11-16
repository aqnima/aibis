document.addEventListener('alpine:init', () => {
    Alpine.data('scraperApp', () => ({
        theme: localStorage.getItem('aibis-theme') || 'light',
        keyword: 'Coffee Shop',
        location: 'Wonosobo',
        limit: 15,
        enrichWebsite: true,
        
        status: 'idle', // idle, running, completed, error
        progress: 0,
        currentCount: 0,
        leads: [],
        logs: [],
        searchFilter: '',
        filterType: 'all', // all, with_phone, with_web, with_social
        totalSavedInDb: 0,
        selectedIds: [],
        
        // Pagination state
        currentPage: 1,
        pageSize: 10,
        
        eventSource: null,

        async init() {
            await this.fetchDbStats();
        },

        async fetchDbStats() {
            try {
                const res = await fetch('/api/leads/count');
                const data = await res.json();
                this.totalSavedInDb = data.total_saved || 0;
            } catch (e) {
                console.error(e);
            }
        },

        async loadSavedLeads() {
            try {
                this.addLog('📁 Memuat seluruh riwayat data yang tersimpan dari database...');
                const res = await fetch('/api/leads/saved');
                const data = await res.json();
                this.leads = data.leads || [];
                this.totalSavedInDb = this.leads.length;
                this.selectedIds = [];
                this.currentPage = 1;
                this.addLog(`✅ Berhasil memuat ${this.leads.length} data tersimpan.`);
            } catch (e) {
                this.addLog(`❌ Gagal memuat database: ${e.message}`);
            }
        },

        async deleteLead(id, name) {
            if (!confirm(`Hapus kontak "${name}" dari database?`)) {
                return;
            }
            try {
                const res = await fetch(`/api/leads/${id}`, { method: 'DELETE' });
                const data = await res.json();
                this.leads = this.leads.filter(l => l.id !== id);
                this.selectedIds = this.selectedIds.filter(i => i !== id);
                this.totalSavedInDb = data.total_saved || 0;
                if (this.currentPage > this.totalPages && this.totalPages > 0) {
                    this.currentPage = this.totalPages;
                }
                this.addLog(`🗑️ Berhasil menghapus: ${name}`);
            } catch (e) {
                this.addLog(`❌ Gagal menghapus data: ${e.message}`);
            }
        },

        async deleteSelected() {
            if (this.selectedIds.length === 0) return;
            if (!confirm(`Hapus ${this.selectedIds.length} data terpilih dari database?`)) {
                return;
            }
            try {
                const res = await fetch('/api/leads/delete-selected', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ids: this.selectedIds })
                });
                const data = await res.json();
                this.leads = this.leads.filter(l => !this.selectedIds.includes(l.id));
                const count = this.selectedIds.length;
                this.selectedIds = [];
                this.totalSavedInDb = data.total_saved || 0;
                if (this.currentPage > this.totalPages && this.totalPages > 0) {
                    this.currentPage = this.totalPages;
                }
                this.addLog(`🗑️ Berhasil menghapus ${count} data terpilih.`);
            } catch (e) {
                this.addLog(`❌ Gagal menghapus data terpilih: ${e.message}`);
            }
        },

        async clearDatabase() {
            if (this.totalSavedInDb === 0 && this.leads.length === 0) {
                alert('Database saat ini sudah kosong.');
                return;
            }
            if (!confirm('PERINGATAN: Kosongkan seluruh riwayat database leads? Data yang dihapus tidak bisa dikembalikan.')) {
                return;
            }
            try {
                const res = await fetch('/api/leads/clear', { method: 'POST' });
                const data = await res.json();
                this.leads = [];
                this.selectedIds = [];
                this.totalSavedInDb = 0;
                this.currentPage = 1;
                this.addLog('🗑️ Seluruh data riwayat database telah dibersihkan.');
            } catch (e) {
                this.addLog(`❌ Gagal membersihkan database: ${e.message}`);
            }
        },

        toggleSelectAll() {
            const pageItemIds = this.paginatedLeads.map(l => l.id);
            const allSelectedOnPage = pageItemIds.every(id => this.selectedIds.includes(id));
            
            if (allSelectedOnPage) {
                this.selectedIds = this.selectedIds.filter(id => !pageItemIds.includes(id));
            } else {
                this.selectedIds = Array.from(new Set([...this.selectedIds, ...pageItemIds]));
            }
        },

        get isAllOnPageSelected() {
            if (this.paginatedLeads.length === 0) return false;
            return this.paginatedLeads.every(l => this.selectedIds.includes(l.id));
        },

        get filteredLeads() {
            return this.leads.filter(lead => {
                const q = this.searchFilter.toLowerCase();
                const matchesSearch = 
                    (lead.name && lead.name.toLowerCase().includes(q)) ||
                    (lead.phone && lead.phone.includes(q)) ||
                    (lead.address && lead.address.toLowerCase().includes(q)) ||
                    (lead.category && lead.category.toLowerCase().includes(q)) ||
                    (lead.email && lead.email.toLowerCase().includes(q));

                if (!matchesSearch) return false;

                if (this.filterType === 'with_phone') return !!lead.phone;
                if (this.filterType === 'with_web') return !!lead.website;
                if (this.filterType === 'with_social') return !!(lead.email || lead.instagram || lead.facebook);
                return true;
            });
        },

        // Pagination Computations
        get totalPages() {
            return Math.ceil(this.filteredLeads.length / this.pageSize) || 1;
        },

        get paginatedLeads() {
            const start = (this.currentPage - 1) * this.pageSize;
            return this.filteredLeads.slice(start, start + this.pageSize);
        },

        get pageStart() {
            if (this.filteredLeads.length === 0) return 0;
            return (this.currentPage - 1) * this.pageSize + 1;
        },

        get pageEnd() {
            return Math.min(this.currentPage * this.pageSize, this.filteredLeads.length);
        },

        nextPage() {
            if (this.currentPage < this.totalPages) {
                this.currentPage++;
            }
        },

        prevPage() {
            if (this.currentPage > 1) {
                this.currentPage--;
            }
        },

        goToPage(p) {
            if (p >= 1 && p <= this.totalPages) {
                this.currentPage = p;
            }
        },

        get stats() {
            const total = this.leads.length;
            if (total === 0) return { total: 0, phoneRate: 0, webRate: 0, socialRate: 0, avgRating: 0 };
            
            const withPhone = this.leads.filter(l => l.phone).length;
            const withWeb = this.leads.filter(l => l.website).length;
            const withSocial = this.leads.filter(l => l.email || l.instagram || l.facebook).length;
            
            const ratings = this.leads.filter(l => l.rating).map(l => l.rating);
            const avgRating = ratings.length > 0 
                ? (ratings.reduce((a, b) => a + b, 0) / ratings.length).toFixed(1) 
                : 0;

            return {
                total,
                phoneRate: Math.round((withPhone / total) * 100),
                webRate: Math.round((withWeb / total) * 100),
                socialRate: Math.round((withSocial / total) * 100),
                avgRating
            };
        },

        async startScraping() {
            if (!this.keyword.trim()) {
                alert('Silakan masukkan kata kunci pencarian!');
                return;
            }

            this.status = 'running';
            this.progress = 0;
            this.currentCount = 0;
            this.leads = [];
            this.selectedIds = [];
            this.logs = [];
            this.currentPage = 1;
            this.addLog(`🚀 Mempersiapkan task scraping: "${this.keyword}" di "${this.location}" (Target: ${this.limit})`);

            try {
                const res = await fetch('/api/scrape/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        keyword: this.keyword,
                        location: this.location,
                        limit: parseInt(this.limit),
                        enrich_website: this.enrichWebsite
                    })
                });

                if (!res.ok) {
                    throw new Error('Gagal memulai scraping pada server.');
                }

                this.connectSSE();

            } catch (err) {
                this.status = 'error';
                this.addLog(`❌ Error: ${err.message}`);
            }
        },

        connectSSE() {
            if (this.eventSource) {
                this.eventSource.close();
            }

            this.eventSource = new EventSource('/api/scrape/stream');

            this.eventSource.onmessage = (event) => {
                const data = JSON.parse(event.data);

                if (data.type === 'log') {
                    this.addLog(data.message);
                } else if (data.type === 'lead') {
                    this.leads.unshift(data.lead);
                    this.currentCount = data.current;
                    this.progress = Math.min(100, Math.round((data.current / data.target) * 100));
                    this.totalSavedInDb++;
                } else if (data.type === 'done') {
                    this.status = 'completed';
                    this.progress = 100;
                    this.addLog('✨ Selesai! Semua data baru telah otomatis tersimpan ke database SQLite.');
                    this.fetchDbStats();
                    this.eventSource.close();
                } else if (data.type === 'error') {
                    this.status = 'error';
                    this.addLog(`❌ Error: ${data.message}`);
                    this.eventSource.close();
                }
            };

            this.eventSource.onerror = () => {
                if (this.status === 'running') {
                    this.status = 'completed';
                }
                this.eventSource.close();
            };
        },

        async stopScraping() {
            try {
                await fetch('/api/scrape/stop', { method: 'POST' });
                this.status = 'idle';
                this.addLog('🛑 Perintah stop dikirim ke server.');
                if (this.eventSource) {
                    this.eventSource.close();
                }
            } catch (e) {
                console.error(e);
            }
        },

        addLog(msg) {
            const time = new Date().toLocaleTimeString();
            this.logs.unshift(`[${time}] ${msg}`);
            if (this.logs.length > 60) this.logs.pop();
        },

        toggleTheme() {
            this.theme = this.theme === 'dark' ? 'light' : 'dark';
            document.documentElement.dataset.theme = this.theme;
            localStorage.setItem('aibis-theme', this.theme);
        },
        downloadExcel(scope = 'current') {
            window.location.href = `/api/export/excel?scope=${scope}`;
        },

        downloadCSV(scope = 'current') {
            window.location.href = `/api/export/csv?scope=${scope}`;
        }
    }));
});
