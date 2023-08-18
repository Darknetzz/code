<?php

class Crypto {

    function encryptwithpw($str, $password) {
        return openssl_encrypt($str,"AES-128-ECB",$password);
    }

    function decryptwithpw($str, $password) {
        return openssl_decrypt($str,"AES-128-ECB",$password);
    }

}

?>