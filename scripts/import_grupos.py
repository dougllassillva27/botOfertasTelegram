from app.storage import load_data, save_data

def run_import():
    new_groups = [
        "promotop", "ctdescontomate", "bugadaopromocoes", "gtofertas",
        "achadinhosnapromoo", "pelandobr", "fraguas84oficial", "cuponsjersu",
        "garimpeirosoficial", "promochina", "kleitechpromos", "canalescolhacerta",
        "vrlofertas", "benchpromos", "ofertasdachina20", "toptechpromo",
        "familiatopsdachina", "meusdscts", "pcdofafapromo", "cuponsdogeek",
        "rapaduraofertas", "promoimporta", "ofertasbrasil20", "ultraofertas",
        "economizanderson", "grupotempromo", "chinofertas"
    ]
    
    state = load_data()
    
    added_count = 0
    for group in new_groups:
        group_clean = group.lower()
        # Evita adicionar grupos que já estão na lista
        if group_clean not in [g.lower() for g in state["grupos"]]:
            state["grupos"].append(group_clean)
            added_count += 1
            
    save_data(state)
    print(f"✅ Import successful! {added_count} new groups added to data.json.")

if __name__ == '__main__':
    run_import()
