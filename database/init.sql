CREATE TABLE IF NOT EXISTS tasks (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title varchar(200) NOT NULL CHECK (length(trim(title)) > 0),
    completed boolean NOT NULL DEFAULT false
);
