<?php

class sql {

/* ────────────────────────────────────────────────────────────────────────── */
/*                                 Connect DB                                 */
/* ────────────────────────────────────────────────────────────────────────── */
function connectDB(string $host, string $user, string $pass, string $db) {
    return new mysqli($host, $user, $pass, $db);
}

/* ────────────────────────────────────────────────────────────────────────── */
/*                 MAIN SQL QUERY WRAPPER [IMPORTANT FUNCTION]                */
/* ────────────────────────────────────────────────────────────────────────── */
function executeQuery(string $statement, array $params = []) {
    global $sqlcon;

    # allow for the statement to contain constants directly (probably not such a good idea)
    # https://stackoverflow.com/questions/1563654/quoting-constants-in-php-this-is-a-my-constant
    $statement = str_replace(array_keys(get_defined_constants(true)['user']), get_defined_constants(true)['user'], $statement);

    $query = $sqlcon->prepare($statement);

    $paramsCount = count($params);
    $paramscs = "No parameters";
    if ($paramsCount > 0) {
        $types = '';
        foreach ($params as $n => $val) { # &$val ?
            $types .= 's';
            $query->bind_param($types, $val);
            # Hey, I know this looks kinda weird, BUT: 
            # https://stackoverflow.com/questions/36777813/using-bind-param-with-arrays-and-loops
        }
        $paramscs = implode(", ", $params);
    }

    $query->execute();
    $result = $query->get_result();

    if ($sqlcon->error) {
        die("<div class='alert alert-danger'>Fatal error: $sqlcon->error</div>");
    }

    if ($result->num_rows < 1) {
        return $result; # we still want to return the object (even if it's empty)
    }

    return $result;
}
/* ────────────────────────────────────────────────────────────────────────── */
}

?>