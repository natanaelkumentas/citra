create table analisis_objek (
    id uuid primary key default gen_random_uuid(),
    
    jumlah_objek integer,
    piksel_objek integer,
    luas double precision,
    
    panjang double precision,
    lebar double precision,
    
    perimeter double precision,
    dispersi double precision,
    
    kebulatan double precision,
    kerampingan double precision,
    
    created_at timestamp default now()
);