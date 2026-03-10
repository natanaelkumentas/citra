create table analisis_gambar (
    id bigint generated always as identity primary key,
    
    mean_r double precision,
    mean_g double precision,
    mean_b double precision,
    
    jumlah_warna_unik integer,
    
    dominan_r integer,
    dominan_g integer,
    dominan_b integer,
    
    created_at timestamp default now()
);