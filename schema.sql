create table
  public.global_inventory (
    gold bigint not null,
    num_capacity bigint not null,
    vol_capacity bigint not null,
    red bigint null,
    green bigint null,
    blue bigint null,
    dark bigint null,
    constraint global_inventory_pkey primary key (gold)
  ) tablespace pg_default;

create table
  public.catalog (
    price integer not null default 50,
    name text not null,
    qty integer not null,
    r integer not null,
    g integer not null,
    b integer not null,
    d integer not null,
    listed boolean not null default false,
    cost_per_vol double precision not null default '0'::double precision,
    constraint catalog_pkey primary key (r, g, b, d),
    constraint catalog_name_key unique (name)
  ) tablespace pg_default;

create table
  public.customers (
    name text not null,
    class text not null,
    level bigint not null,
    constraint customers_pkey primary key (name),
    constraint customers_name_key unique (name)
  ) tablespace pg_default;

create table
  public.visits (
    name text not null,
    visit_time timestamp with time zone not null default now(),
    visit_id bigint not null,
    constraint visits_pkey primary key (name, visit_id),
    constraint visits_name_fkey foreign key (name) references customers (name)
  ) tablespace pg_default;

create table
  public.carts (
    cart_id bigint generated by default as identity not null,
    created_at timestamp with time zone not null default now(),
    name text not null,
    purchased boolean not null default false,
    constraint shopping_cart_pkey primary key (cart_id),
    constraint shopping_cart_cart_id_key unique (cart_id),
    constraint cart_name_fkey foreign key (name) references customers (name)
  ) tablespace pg_default;

create table
  public.ledger (
    cart_id bigint not null,
    r integer not null,
    g integer not null,
    b integer not null,
    d integer not null,
    sold bigint not null default '0'::bigint,
    ledger_id bigint generated by default as identity not null,
    price bigint not null default '0'::bigint,
    ordered bigint not null default '0'::bigint,
    constraint cart_items_pkey primary key (ledger_id),
    constraint cart_items_cart_id_fkey foreign key (cart_id) references carts (cart_id),
    constraint cart_items_r_g_b_d_fkey foreign key (r, g, b, d) references catalog (r, g, b, d)
  ) tablespace pg_default;

create table
  public.strategy (
    day integer not null,
    red_ratio double precision not null,
    green_ratio double precision not null,
    blue_ratio double precision not null,
    dark_ratio double precision not null,
    day_name text not null,
    deviation integer null,
    is_today boolean null,
    constraint strategy_pkey primary key (day),
    constraint strategy_day_key unique (day)
  ) tablespace pg_default;

create table
  public.strategy_potions (
    day integer not null,
    r integer not null,
    g integer not null,
    b integer not null,
    d integer not null,
    constraint strategy_potions_pkey primary key (day, r, g, b, d),
    constraint strategy_potions_day_fkey foreign key (day) references strategy (day),
    constraint strategy_potions_r_g_b_d_fkey foreign key (r, g, b, d) references catalog (r, g, b, d)
  ) tablespace pg_default;