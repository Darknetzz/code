<?php


/*
Usage:

include "<NAME_OF_THIS_FILE>";
use PHP\Utils

*/


namespace PHP\Utils;

/* ────────────────────────────────────────────────────────────────────────── */
/*                                 StringUtil                                 */
/* ────────────────────────────────────────────────────────────────────────── */
class StringUtil {

    public function slugify($str) {
        $str = preg_replace('/[^A-Za-z0-9\-]/', '', $str);
        return $str;
    }

}

/* ────────────────────────────────────────────────────────────────────────── */
/*                                  FuncUtil                                  */
/* ────────────────────────────────────────────────────────────────────────── */
class FuncUtil {

    function countFunctionParams(string $functionName) : int {
        $reflection = new ReflectionFunction();
        $paramCount = $reflection->getNumberOfParameters($functionName);
        return $paramCount;
    }

}

/* ────────────────────────────────────────────────────────────────────────── */
/*                                   VarUtil                                  */
/* ────────────────────────────────────────────────────────────────────────── */
class VarUtil {

    function var_assert(mixed &$var, mixed $assertVal = false, bool $lazy = false) : bool {
        if (!isset($var)) {
            return false;
        }
    
        if ($assertVal != false || func_num_args() > 1) {
    
            if ($lazy != false) {
                return $var == $assertVal;
            }
    
            return $var === $assertVal;
        }
        
        return true;
    }

}


/* ────────────────────────────────────────────────────────────────────────── */
/*                                  TimeUtil                                  */
/* ────────────────────────────────────────────────────────────────────────── */
class TimeUtil {
    function getCurrentTime(string $format, string $timezone) : string {
        $dt = new DateTime('now');
        $tz = new DateTimeZone($timezone);
        $dt->setTimeZone($tz);
        $return = $dt->format($format);
    
        return $return;
    }
}

?>