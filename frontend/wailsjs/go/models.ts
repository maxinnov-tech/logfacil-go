export namespace config {
	
	export class LogMarker {
	    pattern: string;
	    level: string;
	    color: string;
	
	    static createFrom(source: any = {}) {
	        return new LogMarker(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.pattern = source["pattern"];
	        this.level = source["level"];
	        this.color = source["color"];
	    }
	}
	export class Settings {
	    last_folder: string;
	    appearance_mode: string;
	    ui_theme: string;
	    auto_update: boolean;
	    font_size: number;
	    scan_interval: number;
	    max_view_lines: number;
	
	    static createFrom(source: any = {}) {
	        return new Settings(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.last_folder = source["last_folder"];
	        this.appearance_mode = source["appearance_mode"];
	        this.ui_theme = source["ui_theme"];
	        this.auto_update = source["auto_update"];
	        this.font_size = source["font_size"];
	        this.scan_interval = source["scan_interval"];
	        this.max_view_lines = source["max_view_lines"];
	    }
	}

}

export namespace main {
	
	export class ServiceState {
	    name: string;
	    running: boolean;
	    message: string;
	
	    static createFrom(source: any = {}) {
	        return new ServiceState(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.name = source["name"];
	        this.running = source["running"];
	        this.message = source["message"];
	    }
	}
	export class ComponentStatus {
	    name: string;
	    is_ok: boolean;
	    status: string;
	    services: ServiceState[];
	
	    static createFrom(source: any = {}) {
	        return new ComponentStatus(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.name = source["name"];
	        this.is_ok = source["is_ok"];
	        this.status = source["status"];
	        this.services = this.convertValues(source["services"], ServiceState);
	    }
	
		convertValues(a: any, classs: any, asMap: boolean = false): any {
		    if (!a) {
		        return a;
		    }
		    if (a.slice && a.map) {
		        return (a as any[]).map(elem => this.convertValues(elem, classs));
		    } else if ("object" === typeof a) {
		        if (asMap) {
		            for (const key of Object.keys(a)) {
		                a[key] = new classs(a[key]);
		            }
		            return a;
		        }
		        return new classs(a);
		    }
		    return a;
		}
	}
	export class PDVResponse {
	    pdvs: parser.PDVInfo[];
	    message: string;
	
	    static createFrom(source: any = {}) {
	        return new PDVResponse(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.pdvs = this.convertValues(source["pdvs"], parser.PDVInfo);
	        this.message = source["message"];
	    }
	
		convertValues(a: any, classs: any, asMap: boolean = false): any {
		    if (!a) {
		        return a;
		    }
		    if (a.slice && a.map) {
		        return (a as any[]).map(elem => this.convertValues(elem, classs));
		    } else if ("object" === typeof a) {
		        if (asMap) {
		            for (const key of Object.keys(a)) {
		                a[key] = new classs(a[key]);
		            }
		            return a;
		        }
		        return new classs(a);
		    }
		    return a;
		}
	}

}

export namespace parser {
	
	export class PDVInfo {
	    codigo: string;
	    id_interno: string;
	    nome: string;
	    tipo: string;
	    operando: boolean;
	    serial: string;
	    codigo_estoque: string;
	    ip: string;
	
	    static createFrom(source: any = {}) {
	        return new PDVInfo(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.codigo = source["codigo"];
	        this.id_interno = source["id_interno"];
	        this.nome = source["nome"];
	        this.tipo = source["tipo"];
	        this.operando = source["operando"];
	        this.serial = source["serial"];
	        this.codigo_estoque = source["codigo_estoque"];
	        this.ip = source["ip"];
	    }
	}

}

export namespace updater {
	
	export class UpdateResponse {
	    has_update: boolean;
	    version: string;
	    download_url: string;
	    release_notes: string;
	    message: string;
	
	    static createFrom(source: any = {}) {
	        return new UpdateResponse(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.has_update = source["has_update"];
	        this.version = source["version"];
	        this.download_url = source["download_url"];
	        this.release_notes = source["release_notes"];
	        this.message = source["message"];
	    }
	}

}

