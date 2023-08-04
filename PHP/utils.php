<?php

class util {

    function countFunctionParams(string $functionName) : int {
        $reflection = new ReflectionFunction();
        $paramCount = $reflection->getNumberOfParameters($functionName);
        return $paramCount;
    }

}

?>