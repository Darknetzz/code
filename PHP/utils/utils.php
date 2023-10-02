<?php


/*
──────────────────────────────────────────────────────────────────────────────────────────────────────────────
[ HOW_TO_USE ] ################ [ HOW_TO_USE ] ################ [ HOW_TO_USE ] ################ [ HOW_TO_USE ]
──────────────────────────────────────────────────────────────────────────────────────────────────────────────

# Import utils
require_once("utils.php");
use Darknetzz\PHPUtils as Utils;
$util = new Utils;

# Examples:

- Slugify
    $string     = "Some test-string_haha :D";
    $slugified  = $util->slugify($string); 
    echo $slugified; # should return "some_test_string_haha"


- countFunctionParams
    $functionName = "strlen";
    $countParams  = $util->countFunctionParams($functionName);
    echo "$functionName has $countParams params.\n";

- var_assert
    $variable = "This is set!";
    $variable2= "But this will not be..."; 
    unset($variable2); 
    echo "\$variable: ".$util->var_assert($variable."\n");  should be true    ("This is set!")
    echo "\$variable2:".$util->var_assert($variable2."\n"); should be false   (null)

──────────────────────────────────────────────────────────────────────────────────────────────────────────────
[ END_HOWTO ] ################## [ END_HOWTO ] ################## [ END_HOWTO ] ################## [ END_HOWTO ]
──────────────────────────────────────────────────────────────────────────────────────────────────────────────
*/

namespace Darknetzz;

/* ────────────────────────────────────────────────────────────────────────── */
/*                                 Class Utils                                */
/* ────────────────────────────────────────────────────────────────────────── */
class PHPUtils 
{
    use Strings;
    use Funcs;
    use Vars;
    use Times;
}



/* ────────────────────────────────────────────────────────────────────────── */
/*                                 StringUtil                                 */
/* ────────────────────────────────────────────────────────────────────────── */
trait Strings {

    /* ────────────────────────────────────────────────────────────────────── */
    /*                                 slugify                                */
    /* ────────────────────────────────────────────────────────────────────── */
    public function slugify(string $string, int $lenCap = 0) {
        $final_string = $string;

        if (strlen($final_string) > $lenCap && $lenCap != 0) {
            $final_string = substr($final_string, 0, ($lenCap - 1));
        }

        $final_string = strtolower($string);
        $final_string = str_replace(['-', ' ', '.'],                 '_',  $final_string);
        $final_string = str_replace(['_____', '____', '___', '__'],  '_',  $final_string);
        $final_string = preg_replace('/[^A-Za-z0-9\_]/',             '',   $final_string);
        return $final_string;
    }

    /* -------------------------------------------------------------------------- */
    /*                               Generate string                              */
    /* -------------------------------------------------------------------------- */
    public function genStr($len = 24, $charset = null, $required = []) {
        $this->returnValue = "";

        if ($charset == null) {
            $charset = $this->str_all;
        }

        if (is_array($charset)) {
            $count = count($charset);
        } elseif (is_string($charset)) {
            $count = strlen($charset);
        } else {
            die("charset for genStr wasn't an array or string.");
        }

        for ($i=0; $i <= $len-1; $i++) {
            $roll = mt_rand(0,$count-1);
            $this->returnValue .= $charset[$roll];
        }

        if (in_array("lower", $required) && !$this->arrayInString($this->str_lowercase, $this->returnValue)) {
            $this->returnValue .= $this->str_lowercase[mt_rand(0,count($this->str_lowercase-1))];
        }
        if (in_array("upper", $required) && !$this->arrayInString($this->str_uppercase, $this->returnValue)) {
            $this->returnValue .= $this->str_uppercase[mt_rand(0,count($this->str_uppercase-1))];
        }
        if (in_array("digit", $required) && !$this->arrayInString($this->str_digits, $this->returnValue)) {
            $this->returnValue .= $this->str_digits[mt_rand(0,count($this->str_digits-1))];
        }
        if (in_array("symbol", $required) && !$this->arrayInString($this->str_symbols, $this->returnValue)) {
            $this->returnValue .= $this->str_symbols[mt_rand(0,count($this->str_symbols-1))];
        }

        $this->returnValue = str_shuffle($this->returnValue); 

        return $this->returnValue;
    }

}
/* ────────────────────────────────────────────────────────────────────────── */




/* ────────────────────────────────────────────────────────────────────────── */
/*                                  FuncUtil                                  */
/* ────────────────────────────────────────────────────────────────────────── */
trait Funcs {

    public function countFunctionParams(string $functionName) : int {
        $reflection = new \ReflectionFunction($functionName);
        $paramCount = $reflection->getNumberOfParameters();
        return $paramCount;
    }

}
/* ────────────────────────────────────────────────────────────────────────── */




/* ────────────────────────────────────────────────────────────────────────── */
/*                                   VarUtil                                  */
/* ────────────────────────────────────────────────────────────────────────── */
trait Vars {

    public function var_assert(mixed &$var, mixed $assertVal = false, bool $lazy = false) : bool {
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





/* ────────────────────────────────────────────────────────────────────────── */
/*                                  TimeUtil                                  */
/* ────────────────────────────────────────────────────────────────────────── */
trait Times {
    public function getCurrentTime(string $format, string $timezone) : string {
        $dt = new DateTime('now');
        $tz = new DateTimeZone($timezone);
        $dt->setTimeZone($tz);
        $return = $dt->format($format);
    
        return $return;
    }
}
/* ────────────────────────────────────────────────────────────────────────── */




?>